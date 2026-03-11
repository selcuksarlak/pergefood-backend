from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.stock_sync import StockSyncLog, StockSyncItemLog
from app.core.config import settings
import json

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

logs = db.query(StockSyncLog).order_by(StockSyncLog.id.desc()).limit(10).all()
for log in logs:
    print(f"Log ID: {log.id}, Status: {log.status}, Processed: {log.products_processed}, Updated: {log.products_updated}, Skipped: {log.products_skipped}, Errors: {log.error_count}")
    if log.errors:
        print(f"  Errors: {log.errors[:200]}...")

db.close()
