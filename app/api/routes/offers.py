from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
import secrets
from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.offer import Offer, OfferItem
from app.models.product import Product
from app.models.user import User
from app.services.pdf_service import PDFOfferService

router = APIRouter(prefix="/offers", tags=["Teklif Yönetimi"])

class OfferItemCreate(BaseModel):
    product_id: int
    quantity: int
    unit_price: Decimal

class OfferCreate(BaseModel):
    customer_name: str
    shipping_cost: Decimal
    items: List[OfferItemCreate]

class OfferItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal

class OfferResponse(BaseModel):
    id: int
    customer_name: str
    date: datetime
    shipping_cost: Decimal
    grand_total: Decimal
    status: str
    public_token: str | None = None
    approved_at: datetime | None = None
    is_notification_read: int = 0
    billing_info: str | None = None
    shipping_address: str | None = None
    items: List[OfferItemResponse]

    class Config:
        from_attributes = True

@router.post("/", response_model=OfferResponse, status_code=201)
def create_offer(
    data: OfferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    grand_total = data.shipping_cost
    for item in data.items:
        grand_total += item.unit_price * item.quantity
    
    offer = Offer(
        customer_name=data.customer_name,
        shipping_cost=data.shipping_cost,
        grand_total=grand_total,
        status="bekliyor",
        public_token=secrets.token_urlsafe(16)
    )
    db.add(offer)
    db.flush()

    response_items = []
    for item_data in data.items:
        product = db.query(Product).filter(Product.id == item_data.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Ürün ID {item_data.product_id} bulunamadı")
        
        total_price = item_data.unit_price * item_data.quantity
        item = OfferItem(
            offer_id=offer.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            total_price=total_price
        )
        db.add(item)
        
        response_items.append({
            "id": 0, # Will be set after commit/refresh if needed
            "product_id": product.id,
            "product_name": product.product_name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "total_price": total_price
        })

    db.commit()
    db.refresh(offer)
    return offer

@router.get("/", response_model=List[OfferResponse])
def list_offers(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return db.query(Offer).order_by(Offer.id.desc()).all()

@router.get("/{offer_id}/pdf")
def get_offer_pdf(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Teklif bulunamadı")
    
    # Prepare data for PDF
    items_data = []
    for item in offer.items:
        items_data.append({
            "product_name": item.product.product_name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "total_price": item.total_price
        })
    
    offer_data = {
        "id": offer.id,
        "customer_name": offer.customer_name,
        "date": offer.date.strftime("%d.%m.%Y"),
        "shipping_cost": offer.shipping_cost,
        "grand_total": offer.grand_total,
        "items": items_data
    }
    
    pdf_service = PDFOfferService()
    filepath = pdf_service.generate_offer_pdf(offer_data)
    
    with open(filepath, "rb") as f:
        pdf_content = f.read()
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=teklif_{offer_id}.pdf"}
    )

@router.delete("/{offer_id}")
def delete_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Teklif bulunamadı")
    db.delete(offer)
    db.commit()
    return {"detail": "Teklif silindi"}

@router.put("/{offer_id}", response_model=OfferResponse)
def update_offer(
    offer_id: int,
    data: OfferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Teklif bulunamadı")
        
    grand_total = data.shipping_cost
    for item in data.items:
        grand_total += item.unit_price * item.quantity

    offer.customer_name = data.customer_name
    offer.shipping_cost = data.shipping_cost
    offer.grand_total = grand_total
    
    # If an offer is updated by staff, we must ALWAYS reset the 'approved' status 
    # so the customer has to re-approve the new terms and items.
    offer.status = "bekliyor"
    offer.approved_at = None
    offer.is_notification_read = 0

    # Wipe existing items
    db.query(OfferItem).filter(OfferItem.offer_id == offer_id).delete()
    db.flush()

    # Re-insert items
    for item_data in data.items:
        product = db.query(Product).filter(Product.id == item_data.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Ürün ID {item_data.product_id} bulunamadı")
            
        total_price = item_data.unit_price * item_data.quantity
        item = OfferItem(
            offer_id=offer.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            total_price=total_price
        )
        db.add(item)
        
    db.commit()
    db.refresh(offer)
    return offer

@router.get("/public/{token}", response_model=OfferResponse)
def get_public_offer(token: str, db: Session = Depends(get_db)):
    offer = db.query(Offer).filter(Offer.public_token == token).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Teklif bulunamadı veya link geçersiz")
    return offer

class PublicApproveRequest(BaseModel):
    billing_info: str
    shipping_address: str

@router.post("/public/{token}/approve")
def approve_public_offer(
    token: str, 
    data: PublicApproveRequest,
    db: Session = Depends(get_db)
):
    offer = db.query(Offer).filter(Offer.public_token == token).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Teklif bulunamadı")
    if offer.status in ["onaylandi", "tamamlandi", "iptal"]:
        raise HTTPException(status_code=400, detail="Bu teklif artık işleme alınamaz")
        
    offer.status = "onaylandi"
    offer.approved_at = datetime.now()
    offer.is_notification_read = 0
    offer.billing_info = data.billing_info
    offer.shipping_address = data.shipping_address
    db.commit()
    return {"detail": "Teklif başarıyla onaylandı"}

@router.get("/notifications", response_model=List[OfferResponse])
def get_unread_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    return db.query(Offer).filter(
        Offer.status == "onaylandi",
        Offer.is_notification_read == 0
    ).order_by(Offer.approved_at.desc()).all()

@router.post("/notifications/read")
def mark_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    unread_offers = db.query(Offer).filter(
        Offer.status == "onaylandi",
        Offer.is_notification_read == 0
    ).all()
    
    for offer in unread_offers:
        offer.is_notification_read = 1
        
    db.commit()
    return {"detail": "Tüm bildirimler okundu olarak işaretlendi"}

class UpdateOfferStatusRequest(BaseModel):
    status: str

@router.patch("/{offer_id}/status", response_model=OfferResponse)
def update_offer_status(
    offer_id: int,
    data: UpdateOfferStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    valid_statuses = ["bekliyor", "onaylandi", "tamamlandi", "iptal"]
    if data.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Geçersiz durum bilgisi")

    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Teklif bulunamadı")
    
    offer.status = data.status
    db.commit()
    db.refresh(offer)
    return offer
