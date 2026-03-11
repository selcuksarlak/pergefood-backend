import os
import json
import joblib
import numpy as np
import pandas as pd
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.security import get_current_active_user, require_role
from app.models.stock import AIPricePrediction, MarketPrice, StockLevel, StockEntry, StockOutput
from app.models.product import Product, ProductCost
from app.models.user import User

router = APIRouter(prefix="/ai", tags=["AI Fiyat Tahmini"])

MODELS_DIR = "app/ml/models"
os.makedirs(MODELS_DIR, exist_ok=True)


class PredictionResponse(BaseModel):
    product_id: int
    product_name: str
    recommended_price: float
    minimum_safe_price: float
    maximum_market_price: Optional[float]
    expected_profit_margin: float
    demand_prediction: str
    model_used: str
    predicted_at: datetime

    class Config:
        from_attributes = True


def _build_features(product_id: int, db: Session) -> Optional[dict]:
    """Build feature vector for ML model from DB data."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return None

    # Latest cost
    latest_cost = (
        db.query(ProductCost)
        .filter(ProductCost.product_id == product_id)
        .order_by(ProductCost.created_at.desc())
        .first()
    )
    if not latest_cost:
        return None

    # Stock level
    stock = db.query(StockLevel).filter(StockLevel.product_id == product_id).first()
    current_stock = float(stock.current_stock) if stock else 0

    # Sales in last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_outputs = (
        db.query(StockOutput)
        .filter(StockOutput.product_id == product_id, StockOutput.output_date >= thirty_days_ago)
        .all()
    )
    units_sold_30d = sum(float(o.quantity) for o in recent_outputs)
    avg_sale_price = (
        sum(float(o.sale_price) for o in recent_outputs) / len(recent_outputs)
        if recent_outputs else float(latest_cost.calculated_price)
    )

    # Market price average
    market_prices = (
        db.query(MarketPrice)
        .filter(MarketPrice.product_id == product_id)
        .order_by(MarketPrice.scraped_at.desc())
        .limit(20)
        .all()
    )
    avg_market_price = (
        sum(float(m.competitor_price) for m in market_prices) / len(market_prices)
        if market_prices else float(latest_cost.calculated_price) * 1.1
    )
    min_market = min((float(m.competitor_price) for m in market_prices), default=None)
    max_market = max((float(m.competitor_price) for m in market_prices), default=None)

    return {
        "real_cost": float(latest_cost.real_cost),
        "current_calc_price": float(latest_cost.calculated_price),
        "profit_margin": float(latest_cost.profit_margin),
        "current_stock": current_stock,
        "min_stock": float(stock.minimum_stock_level) if stock else 10,
        "units_sold_30d": units_sold_30d,
        "avg_sale_price": avg_sale_price,
        "avg_market_price": avg_market_price,
        "min_market_price": min_market or float(latest_cost.calculated_price),
        "max_market_price": max_market or float(latest_cost.calculated_price) * 1.2,
    }


def _rule_based_prediction(features: dict) -> dict:
    """
    Rule-based prediction fallback when ML model is not yet trained.
    Uses cost, margin, market prices, and stock level to derive recommendations.
    """
    real_cost = features["real_cost"]
    avg_market = features["avg_market_price"]
    units_sold = features["units_sold_30d"]
    current_stock = features["current_stock"]
    min_stock = features["min_stock"]

    # Minimum safe = cost + 5% buffer
    minimum_safe = real_cost * 1.05

    # Recommended: blend our calculated price with market
    our_price = features["current_calc_price"]
    recommended = (our_price * 0.6 + avg_market * 0.4)

    # If stock is low, we can charge more; if high stock, compete
    stock_ratio = current_stock / max(min_stock, 1)
    if stock_ratio < 0.5:
        recommended *= 1.05   # low stock premium
    elif stock_ratio > 3:
        recommended *= 0.97   # high stock slight discount

    max_market = features["max_market_price"]
    margin = ((recommended - real_cost) / real_cost * 100) if real_cost > 0 else 0

    # Demand prediction
    if units_sold > 50:
        demand = "Yüksek"
    elif units_sold > 10:
        demand = "Orta"
    else:
        demand = "Düşük"

    return {
        "recommended_price": round(recommended, 2),
        "minimum_safe_price": round(minimum_safe, 2),
        "maximum_market_price": round(max_market, 2),
        "expected_profit_margin": round(margin, 2),
        "demand_prediction": demand,
        "model_used": "rule_based_v1",
    }


def _ml_prediction(features: dict) -> Optional[dict]:
    """Try to load and use a trained sklearn model."""
    model_path = os.path.join(MODELS_DIR, "price_model.joblib")
    if not os.path.exists(model_path):
        return None
    try:
        model = joblib.load(model_path)
        feature_cols = [
            "real_cost", "profit_margin", "current_stock",
            "units_sold_30d", "avg_market_price", "avg_sale_price"
        ]
        X = np.array([[features[c] for c in feature_cols]])
        pred_price = float(model.predict(X)[0])
        real_cost = features["real_cost"]
        margin = ((pred_price - real_cost) / real_cost * 100) if real_cost > 0 else 0
        return {
            "recommended_price": round(pred_price, 2),
            "minimum_safe_price": round(real_cost * 1.05, 2),
            "maximum_market_price": round(features["max_market_price"], 2),
            "expected_profit_margin": round(margin, 2),
            "demand_prediction": "Orta",
            "model_used": "random_forest_v1",
        }
    except Exception:
        return None


@router.get("/predict/{product_id}", response_model=PredictionResponse)
def predict_price(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")

    features = _build_features(product_id, db)
    if not features:
        raise HTTPException(status_code=422, detail="Ürün için maliyet verisi bulunamadı. Önce maliyet ekleyin.")

    # Try ML model first, fallback to rule-based
    result = _ml_prediction(features) or _rule_based_prediction(features)

    # Persist prediction
    prediction = AIPricePrediction(
        product_id=product_id,
        recommended_price=Decimal(str(result["recommended_price"])),
        minimum_safe_price=Decimal(str(result["minimum_safe_price"])),
        maximum_market_price=Decimal(str(result["maximum_market_price"])) if result["maximum_market_price"] else None,
        expected_profit_margin=Decimal(str(result["expected_profit_margin"])),
        demand_prediction=result["demand_prediction"],
        model_used=result["model_used"],
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)

    return {
        **result,
        "product_id": product_id,
        "product_name": product.product_name,
        "predicted_at": prediction.predicted_at,
    }


@router.post("/train", status_code=202)
def train_model(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    """Trigger background retraining of the price prediction model."""
    background_tasks.add_task(_train_model_task, db)
    return {"detail": "Model eğitimi arka planda başlatıldı"}


def _train_model_task(db: Session):
    """Background task: train Random Forest on historical data."""
    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.model_selection import train_test_split

        rows = []
        products = db.query(Product).filter(Product.active_status == True).all()
        for product in products:
            features = _build_features(product.id, db)
            if not features:
                continue
            rows.append({
                "real_cost": features["real_cost"],
                "profit_margin": features["profit_margin"],
                "current_stock": features["current_stock"],
                "units_sold_30d": features["units_sold_30d"],
                "avg_market_price": features["avg_market_price"],
                "avg_sale_price": features["avg_sale_price"],
                "target_price": features["avg_sale_price"],
            })

        if len(rows) < 5:
            return  # Not enough data

        df = pd.DataFrame(rows)
        feature_cols = [
            "real_cost", "profit_margin", "current_stock",
            "units_sold_30d", "avg_market_price", "avg_sale_price"
        ]
        X = df[feature_cols]
        y = df["target_price"]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)

        os.makedirs(MODELS_DIR, exist_ok=True)
        joblib.dump(model, os.path.join(MODELS_DIR, "price_model.joblib"))
    except Exception as e:
        print(f"Model training failed: {e}")
