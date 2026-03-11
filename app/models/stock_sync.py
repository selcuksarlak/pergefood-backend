"""
Stock XML Sync — dedicated models
StockSyncLog  : per-run summary (replaces & extends XMLSyncLog for stock feeds)
StockSyncAlert: generated when stock drops >30% or goes below minimum
"""

from sqlalchemy import Column, Integer, Unicode, Boolean, Float, DateTime, UnicodeText, Numeric, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class StockSyncLog(Base):
    __tablename__ = "stock_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    sync_date = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Unicode(20), default="running")       # running / success / error / partial
    source_url = Column(Unicode(500), nullable=True)

    products_processed = Column(Integer, default=0)      # total XML items
    products_updated = Column(Integer, default=0)        # stock level changed
    products_added = Column(Integer, default=0)          # new products created (if allowed)
    products_skipped = Column(Integer, default=0)        # not found in DB / invalid
    alerts_generated = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    errors = Column(UnicodeText, nullable=True)                 # JSON list

    # Relationships
    item_logs = relationship("StockSyncItemLog", back_populates="sync_log", cascade="all, delete-orphan")
    alerts = relationship("StockSyncAlert", back_populates="sync_log")


class StockSyncItemLog(Base):
    """Per-product result of a stock sync run."""
    __tablename__ = "stock_sync_item_logs"

    id = Column(Integer, primary_key=True, index=True)
    sync_log_id = Column(Integer, ForeignKey("stock_sync_logs.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    product_code = Column(Unicode(50), nullable=True)
    product_name = Column(Unicode(200), nullable=True)

    xml_stock = Column(Numeric(10, 3), nullable=True)    # value from XML
    prev_stock = Column(Numeric(10, 3), nullable=True)   # DB value before update
    new_stock = Column(Numeric(10, 3), nullable=True)    # DB value after update
    drop_pct = Column(Float, nullable=True)              # negative = drop, positive = rise

    result = Column(Unicode(30), nullable=True)   # updated / skipped / not_found / invalid / alert
    note = Column(Unicode(300), nullable=True)

    sync_log = relationship("StockSyncLog", back_populates="item_logs")


class StockSyncAlert(Base):
    """Alert generated when stock drops significantly or falls below minimum."""
    __tablename__ = "stock_sync_alerts"

    id = Column(Integer, primary_key=True, index=True)
    sync_log_id = Column(Integer, ForeignKey("stock_sync_logs.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    alert_type = Column(Unicode(30), nullable=False)   # drop_alert / below_minimum / out_of_stock
    alert_message = Column(Unicode(500), nullable=False)

    prev_stock = Column(Numeric(10, 3), nullable=True)
    current_stock = Column(Numeric(10, 3), nullable=True)
    minimum_stock = Column(Numeric(10, 3), nullable=True)
    drop_pct = Column(Float, nullable=True)

    is_acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sync_log = relationship("StockSyncLog", back_populates="alerts")
