from sqlalchemy import Column, Integer, Unicode, Boolean, Numeric, Float
from app.core.database import Base

class Shipping(Base):
    __tablename__ = "shipping_methods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Unicode(100), nullable=False)
    price = Column(Numeric(10, 2), default=0)
    is_active = Column(Boolean, default=True)

    # Gelişmiş Seçenekler
    min_order_amount = Column(Numeric(10, 2), default=0)  # Ücretsiz kargo sınırı
    max_desi = Column(Float, default=0)                  # Maksimum desi
    desi_price = Column(Numeric(10, 2), default=0)       # Desi bazlı fiyat
