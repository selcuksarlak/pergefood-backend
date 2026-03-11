from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.xml_feed import XMLSyncLog
from app.core.config import settings
import json
import sys

# Ensure UTF-8 output for Turkish characters
sys.stdout.reconfigure(encoding='utf-8')

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

logs = db.query(XMLSyncLog).order_by(XMLSyncLog.id.desc()).limit(1).all()
for log in logs:
    print(f"Log ID: {log.id}, Status: {log.status}, Fetch: {log.products_fetched}, Created: {log.products_created}, Updated: {log.products_updated}, Skipped: {log.products_skipped}, Errors: {log.error_count}")
    if log.error_detail:
        try:
            errors = json.loads(log.error_detail)
            print("\nFirst 20 Errors:")
            for i, err in enumerate(errors[:20]):
                print(f"{i+1}: {err}")
        except:
            print(f"  Error Detail (raw): {log.error_detail[:500]}...")

db.close()
