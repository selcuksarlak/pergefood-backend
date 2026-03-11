from sqlalchemy import Column, Integer, Unicode, Float, ForeignKey, DateTime, Numeric, UnicodeText
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class StockEntry(Base):
    __tablename__ = "stock_entries"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False)
    unit_cost = Column(Numeric(10, 4), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    invoice_number = Column(Unicode(100), nullable=True)
    invoice_date = Column(DateTime(timezone=True), nullable=True)
    supplier_name = Column(Unicode(200), nullable=True)
    entry_date = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(UnicodeText, nullable=True)

    product = relationship("Product", back_populates="stock_entries")
    supplier = relationship("Supplier", back_populates="stock_entries")
    invoice = relationship("Invoice", back_populates="stock_entries")


class StockOutput(Base):
    __tablename__ = "stock_outputs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False)
    sale_price = Column(Numeric(10, 4), nullable=False)
    customer = Column(Unicode(200), nullable=True)
    output_date = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(UnicodeText, nullable=True)

    product = relationship("Product", back_populates="stock_outputs")


class StockLevel(Base):
    __tablename__ = "stock_levels"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), unique=True, nullable=False)
    current_stock = Column(Numeric(10, 3), default=0)
    manual_stock = Column(Numeric(10, 3), default=0)
    reserved_stock = Column(Numeric(10, 3), default=0)
    minimum_stock_level = Column(Numeric(10, 3), default=10)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    product = relationship("Product", back_populates="stock_level")

    @property
    def is_low(self) -> bool:
        total = float(self.current_stock or 0) + float(self.manual_stock or 0)
        return total <= float(self.minimum_stock_level or 0)

class MarketPrice(Base):
    __tablename__ = "market_prices"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    competitor_name = Column(Unicode(200), nullable=False)
    product_name_on_site = Column(Unicode(300), nullable=False)
    competitor_price = Column(Numeric(10, 4), nullable=False)
    website_source = Column(Unicode(500), nullable=True)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="market_prices")


class AIPricePrediction(Base):
    __tablename__ = "ai_price_predictions"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    recommended_price = Column(Numeric(10, 4), nullable=False)
    minimum_safe_price = Column(Numeric(10, 4), nullable=False)
    maximum_market_price = Column(Numeric(10, 4), nullable=True)
    expected_profit_margin = Column(Numeric(5, 2), nullable=True)
    demand_prediction = Column(Unicode(50), nullable=True)  # high / medium / low
    model_used = Column(Unicode(50), nullable=True)
    predicted_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="ai_predictions")
