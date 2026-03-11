"""
XMLFeedConfig  — configurable XML feed sources with field mappings
XMLSyncLog     — history of each synchronisation run
XMLFeedImage   — downloaded product images from XML
"""

import json
from sqlalchemy import (
    Column, Integer, Unicode, Boolean, Float,
    DateTime, UnicodeText, JSON, ForeignKey, Numeric
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class XMLFeedConfig(Base):
    __tablename__ = "xml_feed_configs"

    id = Column(Integer, primary_key=True, index=True)

    # Feed identity
    name = Column(Unicode(100), nullable=False)          # e.g. "Pergefood Ürün Feed"
    feed_type = Column(Unicode(50), default="product_list")  # product_list / stock_update / price_update / category_list
    url = Column(Unicode(500), nullable=False)            # base URL
    custom_param = Column(Unicode(200), nullable=True)    # ?custom=OrnekXML

    # Schedule
    is_active = Column(Boolean, default=True)
    sync_interval_minutes = Column(Integer, default=60)  # 30 or 60

    # XML field → DB field mapping (stored as JSON)
    # e.g.: {"urun_adi": "product_name", "urun_kodu": "product_code", "stok": "stock_quantity", "fiyat": "purchase_price"}
    field_mapping = Column(JSON, nullable=True)

    # Root element / item element names to parse
    root_element = Column(Unicode(100), default="products")   # <products>(...)</products>
    item_element = Column(Unicode(100), default="product")    # <product>...</product>

    # Image download settings
    download_images = Column(Boolean, default=True)
    image_save_dir = Column(Unicode(300), default="static/product_images")

    # Runtime
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_status = Column(Unicode(20), nullable=True)  # success / error / running

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    sync_logs = relationship("XMLSyncLog", back_populates="feed_config", cascade="all, delete-orphan")


class XMLSyncLog(Base):
    __tablename__ = "xml_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    feed_config_id = Column(Integer, ForeignKey("xml_feed_configs.id"), nullable=False)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Unicode(20), default="running")   # running / success / error / partial

    # Counts
    products_fetched = Column(Integer, default=0)
    products_created = Column(Integer, default=0)
    products_updated = Column(Integer, default=0)
    products_skipped = Column(Integer, default=0)
    products_flagged = Column(Integer, default=0)   # validation failures → manual review
    images_downloaded = Column(Integer, default=0)
    error_count = Column(Integer, default=0)

    error_detail = Column(UnicodeText, nullable=True)       # JSON list of error messages
    raw_url = Column(Unicode(500), nullable=True)     # actual URL used

    feed_config = relationship("XMLFeedConfig", back_populates="sync_logs")


class XMLProductImage(Base):
    __tablename__ = "xml_product_images"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    original_url = Column(Unicode(500), nullable=False)
    local_path = Column(Unicode(500), nullable=True)
    downloaded_at = Column(DateTime(timezone=True), server_default=func.now())
    is_primary = Column(Boolean, default=False)
