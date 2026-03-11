from sqlalchemy import Column, Integer, Unicode, Boolean, Float, ForeignKey, DateTime, Numeric, UnicodeText, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class UnitType(str, enum.Enum):
    kg = "kg"
    lt = "lt"
    adet = "adet"
    koli = "koli"
    paket = "paket"
    gram = "gram"
    ml = "ml"


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(Unicode(200), nullable=False, index=True)
    
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    
    product_code = Column(Unicode(50), unique=True, nullable=False)
    barcode = Column(Unicode(50), unique=True, nullable=True)
    unit_type = Column(Enum(UnitType), default=UnitType.adet, nullable=False)
    package_size = Column(Float, nullable=True)
    active_status = Column(Boolean, default=True)
    
    # Fiyatlandırma Alanları
    purchase_price = Column(Numeric(10, 4), default=0)
    profit_margin_percent = Column(Numeric(5, 2), default=35.0)
    manual_profit = Column(Numeric(10, 4), default=0)
    shipping_cost = Column(Numeric(10, 4), default=0)
    calculated_sale_price = Column(Numeric(10, 4), default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    costs = relationship("ProductCost", back_populates="product", cascade="all, delete-orphan")
    stock_entries = relationship("StockEntry", back_populates="product")
    stock_outputs = relationship("StockOutput", back_populates="product")
    stock_level = relationship("StockLevel", back_populates="product", uselist=False)
    market_prices = relationship("MarketPrice", back_populates="product")
    ai_predictions = relationship("AIPricePrediction", back_populates="product")
    category = relationship("Category")
    brand = relationship("Brand")

    @property
    def is_xml_price(self):
        # If there are no manual stock entries (invoices), the price must have come from XML.
        return len(self.stock_entries) == 0


class ProductCost(Base):
    __tablename__ = "product_costs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    raw_material = Column(Numeric(10, 4), default=0)
    packaging = Column(Numeric(10, 4), default=0)
    labor = Column(Numeric(10, 4), default=0)
    energy = Column(Numeric(10, 4), default=0)
    transport = Column(Numeric(10, 4), default=0)
    storage = Column(Numeric(10, 4), default=0)
    distribution = Column(Numeric(10, 4), default=0)
    other = Column(Numeric(10, 4), default=0)
    real_cost = Column(Numeric(10, 4), nullable=False)  # sum of all above
    profit_margin = Column(Numeric(5, 2), default=35.0)  # %
    calculated_price = Column(Numeric(10, 4), nullable=False)  # real_cost * (1 + margin/100)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(UnicodeText, nullable=True)

    product = relationship("Product", back_populates="costs")
