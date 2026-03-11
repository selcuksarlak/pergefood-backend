from sqlalchemy import Column, Integer, Unicode, Float, ForeignKey, DateTime, Numeric, UnicodeText
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    supplier_name = Column(Unicode(200), nullable=False, index=True)
    contact_person = Column(Unicode(150), nullable=True)
    phone = Column(Unicode(30), nullable=True)
    email = Column(Unicode(100), nullable=True)
    address = Column(UnicodeText, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    invoices = relationship("Invoice", back_populates="supplier")
    stock_entries = relationship("StockEntry", back_populates="supplier")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    invoice_number = Column(Unicode(100), nullable=True, index=True)
    invoice_date = Column(DateTime(timezone=True), nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=True)
    pdf_path = Column(Unicode(500), nullable=True)
    raw_ocr_text = Column(UnicodeText, nullable=True)
    processing_status = Column(Unicode(30), default="pending")  # pending | processing | done | error
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    supplier = relationship("Supplier", back_populates="invoices")
    invoice_items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    stock_entries = relationship("StockEntry", back_populates="invoice")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)  # nullable until matched
    raw_product_name = Column(Unicode(300), nullable=False)   # as extracted from PDF
    quantity = Column(Numeric(10, 3), nullable=False)
    unit_price = Column(Numeric(10, 4), nullable=False)
    total_price = Column(Numeric(12, 4), nullable=False)
    match_score = Column(Float, nullable=True)   # fuzzy match confidence
    match_status = Column(Unicode(20), default="unmatched")  # matched | unmatched | new_suggestion

    invoice = relationship("Invoice", back_populates="invoice_items")
