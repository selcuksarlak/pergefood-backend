from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from decimal import Decimal
from app.core.database import get_db
from app.core.security import get_current_active_user, require_role
from app.models.shipping import Shipping
from app.models.user import User

router = APIRouter(prefix="/shipping", tags=["Nakliye Yönetimi"])

class ShippingBase(BaseModel):
    name: str
    price: Decimal
    is_active: bool = True
    min_order_amount: Decimal = Decimal("0")
    max_desi: float = 0.0
    desi_price: Decimal = Decimal("0")

class ShippingCreate(ShippingBase):
    pass

class ShippingResponse(ShippingBase):
    id: int

    class Config:
        from_attributes = True

@router.get("/", response_model=List[ShippingResponse])
def list_shipping_methods(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return db.query(Shipping).all()

@router.post("/", response_model=ShippingResponse, status_code=201)
def create_shipping_method(
    data: ShippingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    shipping = Shipping(**data.model_dump())
    db.add(shipping)
    db.commit()
    db.refresh(shipping)
    return shipping

@router.put("/{shipping_id}", response_model=ShippingResponse)
def update_shipping_method(
    shipping_id: int,
    data: ShippingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    shipping = db.query(Shipping).filter(Shipping.id == shipping_id).first()
    if not shipping:
        raise HTTPException(status_code=404, detail="Nakliye yöntemi bulunamadı")
    for field, value in data.model_dump().items():
        setattr(shipping, field, value)
    db.commit()
    db.refresh(shipping)
    return shipping

@router.delete("/{shipping_id}")
def delete_shipping_method(
    shipping_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    shipping = db.query(Shipping).filter(Shipping.id == shipping_id).first()
    if not shipping:
        raise HTTPException(status_code=404, detail="Nakliye yöntemi bulunamadı")
    db.delete(shipping)
    db.commit()
    return {"detail": "Nakliye yöntemi silindi"}
