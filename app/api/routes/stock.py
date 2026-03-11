from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_active_user, require_role
from app.models.stock import StockEntry, StockOutput, StockLevel
from app.models.product import Product
from app.models.user import User

router = APIRouter(prefix="/stock", tags=["Stok Yönetimi"])


class StockEntryCreate(BaseModel):
    product_id: int
    quantity: Decimal
    unit_cost: Decimal
    supplier_id: Optional[int] = None
    invoice_id: Optional[int] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[datetime] = None
    supplier_name: Optional[str] = None
    notes: Optional[str] = None


class StockOutputCreate(BaseModel):
    product_id: int
    quantity: Decimal
    sale_price: Decimal
    customer: Optional[str] = None
    notes: Optional[str] = None


class StockEntryResponse(BaseModel):
    id: int
    product_id: int
    quantity: Decimal
    unit_cost: Decimal
    supplier_id: Optional[int]
    invoice_id: Optional[int]
    invoice_number: Optional[str]
    invoice_date: Optional[datetime]
    supplier_name: Optional[str]
    entry_date: datetime
    notes: Optional[str]

    class Config:
        from_attributes = True


class StockOutputResponse(BaseModel):
    id: int
    product_id: int
    quantity: Decimal
    sale_price: Decimal
    customer: Optional[str]
    output_date: datetime
    notes: Optional[str]

    class Config:
        from_attributes = True


class StockLevelResponse(BaseModel):
    product_id: int
    product_name: Optional[str] = None
    current_stock: Decimal
    manual_stock: Decimal
    reserved_stock: Decimal
    minimum_stock_level: Decimal
    is_low: bool

    class Config:
        from_attributes = True


def _update_stock_level(db: Session, product_id: int, delta: Decimal, is_manual_entry: bool = False):
    """Add or subtract from stock level, creating entry if not exists."""
    level = db.query(StockLevel).filter(StockLevel.product_id == product_id).first()
    if not level:
        level = StockLevel(product_id=product_id, current_stock=0, manual_stock=0)
        db.add(level)
        db.flush()
        
    if is_manual_entry:
        if level.manual_stock is None:
            level.manual_stock = 0
        level.manual_stock = Decimal(str(level.manual_stock)) + delta
    else:
        # Output logic -> decrease manual stock first, then current_stock
        if delta < 0:
            abs_delta = abs(delta)
            manual = Decimal(str(level.manual_stock or 0))
            if manual >= abs_delta:
                level.manual_stock = manual - abs_delta
            else:
                level.manual_stock = 0
                rem_delta = abs_delta - manual
                level.current_stock = Decimal(str(level.current_stock or 0)) - rem_delta
        else:
            level.current_stock = Decimal(str(level.current_stock or 0)) + delta

    total_stock = Decimal(str(level.current_stock or 0)) + Decimal(str(level.manual_stock or 0))
    if total_stock < 0:
        raise HTTPException(status_code=400, detail="Genel stok yetersiz")


@router.post("/entry", response_model=StockEntryResponse, status_code=201)
def create_stock_entry(
    data: StockEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "warehouse"))
):
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
        
    entry = StockEntry(**data.model_dump())
    db.add(entry)
    _update_stock_level(db, data.product_id, data.quantity, is_manual_entry=True)
    
    # Update Product Prices (Son Güncel Fiyatı Yakalama)
    product.purchase_price = data.unit_cost
    # Final price = (PurchasePrice + ManualProfit + ShippingCost) / (1 - Margin/100)
    margin = Decimal(str(product.profit_margin_percent or 0)) / 100
    if margin >= 1: margin = Decimal("0.999")
    
    manual_p = Decimal(str(product.manual_profit or 0))
    shipping = Decimal(str(product.shipping_cost or 0))
    
    product.calculated_sale_price = (data.unit_cost + manual_p + shipping) / (1 - margin)
    
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/output", response_model=StockOutputResponse, status_code=201)
def create_stock_output(
    data: StockOutputCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "warehouse"))
):
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    output = StockOutput(**data.model_dump())
    db.add(output)
    _update_stock_level(db, data.product_id, -data.quantity, is_manual_entry=False)
    db.commit()
    db.refresh(output)
    return output


@router.get("/levels", response_model=List[StockLevelResponse])
def get_stock_levels(
    low_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    levels = db.query(StockLevel).options(joinedload(StockLevel.product)).order_by(StockLevel.product_id).all()
    result = []
    for level in levels:
        total_stock = Decimal(str(level.current_stock or 0)) + Decimal(str(level.manual_stock or 0))
        is_low = total_stock < Decimal(str(level.minimum_stock_level))
        if low_only and not is_low:
            continue
        result.append({
            "product_id": level.product_id,
            "product_name": level.product.product_name if level.product else None,
            "current_stock": level.current_stock or 0,
            "manual_stock": level.manual_stock or 0,
            "reserved_stock": level.reserved_stock or 0,
            "minimum_stock_level": level.minimum_stock_level,
            "is_low": is_low,
        })
    return result


@router.get("/levels/{product_id}", response_model=StockLevelResponse)
def get_product_stock_level(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    level = db.query(StockLevel).options(joinedload(StockLevel.product)).filter(StockLevel.product_id == product_id).first()
    if not level:
        raise HTTPException(status_code=404, detail="Stok kaydı bulunamadı")
        
    total_stock = Decimal(str(level.current_stock or 0)) + Decimal(str(level.manual_stock or 0))
    is_low = total_stock < Decimal(str(level.minimum_stock_level))
    return {
        "product_id": level.product_id,
        "product_name": level.product.product_name if level.product else None,
        "current_stock": level.current_stock or 0,
        "manual_stock": level.manual_stock or 0,
        "reserved_stock": level.reserved_stock or 0,
        "minimum_stock_level": level.minimum_stock_level,
        "is_low": is_low,
    }


@router.get("/entries", response_model=List[StockEntryResponse])
def list_stock_entries(
    product_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    q = db.query(StockEntry)
    if product_id:
        q = q.filter(StockEntry.product_id == product_id)
    return q.order_by(StockEntry.entry_date.desc()).offset(skip).limit(limit).all()


@router.get("/outputs", response_model=List[StockOutputResponse])
def list_stock_outputs(
    product_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    q = db.query(StockOutput)
    if product_id:
        q = q.filter(StockOutput.product_id == product_id)
    return q.order_by(StockOutput.output_date.desc()).offset(skip).limit(limit).all()
