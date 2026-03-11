from sqlalchemy import Column, Integer, Unicode, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Offer(Base):
    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(Unicode(200), nullable=False)
    date = Column(DateTime(timezone=True), server_default=func.now())
    shipping_cost = Column(Numeric(10, 2), default=0)
    grand_total = Column(Numeric(10, 2), default=0)
    status = Column(Unicode(50), default="bekliyor", nullable=False) # bekliyor, onaylandi, reddedildi, iptal
    approved_at = Column(DateTime(timezone=True), nullable=True)
    is_notification_read = Column(Integer, default=0, nullable=False) # 0 for false, 1 for true using Integer to align with BIT
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    billing_info = Column(Unicode(2000), nullable=True) # Will store JSON string with billing/tax details
    shipping_address = Column(Unicode(1000), nullable=True)
    public_token = Column(Unicode(64), unique=True, index=True, nullable=True)

    # Relationships
    items = relationship("OfferItem", back_populates="offer", cascade="all, delete-orphan")

class OfferItem(Base):
    __tablename__ = "offer_items"

    id = Column(Integer, primary_key=True, index=True)
    offer_id = Column(Integer, ForeignKey("offers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)

    offer = relationship("Offer", back_populates="items")
    product = relationship("Product")

    @property
    def product_name(self):
        return self.product.product_name if self.product else "Bilinmeyen Ürün"
