from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.product import Product, ProductCost
from app.models.stock import StockEntry, StockOutput, StockLevel, MarketPrice, AIPricePrediction
from app.models.user import User

router = APIRouter(prefix="/analytics", tags=["Analitik Dashboard"])


class KPIResponse(BaseModel):
    total_products: int
    total_stock_value: float
    low_stock_count: int
    avg_profit_margin: float
    total_stock_entries_30d: int
    total_stock_outputs_30d: int


class TopProductResponse(BaseModel):
    product_id: int
    product_name: str
    units_sold: float
    revenue: float
    margin: Optional[float]


class MarketSummaryResponse(BaseModel):
    product_id: int
    product_name: str
    our_price: Optional[float]
    avg_market_price: Optional[float]
    min_market_price: Optional[float]
    max_market_price: Optional[float]
    price_gap_pct: Optional[float]


@router.get("/kpi", response_model=KPIResponse)
def get_kpi(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    total_products = db.query(Product).filter(Product.active_status == True).count()

    # Total stock value = sum(current_stock * latest unit_cost)
    levels = db.query(StockLevel).all()
    total_value = 0.0
    low_count = 0
    for level in levels:
        current = float(level.current_stock)
        minimum = float(level.minimum_stock_level)
        if current < minimum:
            low_count += 1
        # Get latest cost for product
        cost = (
            db.query(ProductCost)
            .filter(ProductCost.product_id == level.product_id)
            .order_by(ProductCost.created_at.desc())
            .first()
        )
        if cost:
            total_value += current * float(cost.real_cost)

    # Average profit margin from all active costs
    avg_margin_result = db.query(func.avg(ProductCost.profit_margin)).scalar()
    avg_margin = float(avg_margin_result) if avg_margin_result else 0.0

    from datetime import datetime, timedelta
    thirty_ago = datetime.utcnow() - timedelta(days=30)
    entries_30d = db.query(StockEntry).filter(StockEntry.entry_date >= thirty_ago).count()
    outputs_30d = db.query(StockOutput).filter(StockOutput.output_date >= thirty_ago).count()

    return {
        "total_products": total_products,
        "total_stock_value": round(total_value, 2),
        "low_stock_count": low_count,
        "avg_profit_margin": round(avg_margin, 2),
        "total_stock_entries_30d": entries_30d,
        "total_stock_outputs_30d": outputs_30d,
    }


@router.get("/top-products", response_model=List[TopProductResponse])
def top_products(limit: int = 10, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    results = (
        db.query(
            StockOutput.product_id,
            func.sum(StockOutput.quantity).label("units_sold"),
            func.sum(StockOutput.quantity * StockOutput.sale_price).label("revenue"),
        )
        .group_by(StockOutput.product_id)
        .order_by(func.sum(StockOutput.quantity * StockOutput.sale_price).desc())
        .limit(limit)
        .all()
    )

    response = []
    for row in results:
        product = db.query(Product).filter(Product.id == row.product_id).first()
        cost = (
            db.query(ProductCost)
            .filter(ProductCost.product_id == row.product_id)
            .order_by(ProductCost.created_at.desc())
            .first()
        )
        margin = float(cost.profit_margin) if cost else None
        response.append({
            "product_id": row.product_id,
            "product_name": product.product_name if product else "—",
            "units_sold": float(row.units_sold),
            "revenue": round(float(row.revenue), 2),
            "margin": margin,
        })
    return response


@router.get("/market-summary", response_model=List[MarketSummaryResponse])
def market_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    products = db.query(Product).filter(Product.active_status == True).all()
    result = []
    for product in products:
        cost = (
            db.query(ProductCost)
            .filter(ProductCost.product_id == product.id)
            .order_by(ProductCost.created_at.desc())
            .first()
        )
        prices = db.query(MarketPrice).filter(MarketPrice.product_id == product.id).all()
        if not prices:
            continue
        competitor_prices = [float(p.competitor_price) for p in prices]
        avg_mkt = sum(competitor_prices) / len(competitor_prices)
        our_price = float(cost.calculated_price) if cost else None
        gap_pct = ((our_price - avg_mkt) / avg_mkt * 100) if our_price and avg_mkt else None
        result.append({
            "product_id": product.id,
            "product_name": product.product_name,
            "our_price": our_price,
            "avg_market_price": round(avg_mkt, 2),
            "min_market_price": round(min(competitor_prices), 2),
            "max_market_price": round(max(competitor_prices), 2),
            "price_gap_pct": round(gap_pct, 2) if gap_pct is not None else None,
        })
    return result
