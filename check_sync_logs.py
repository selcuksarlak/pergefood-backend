
import sys
sys.path.insert(0, '.')
from app.core.database import SessionLocal
from app.models.xml_feed import XMLSyncLog

db = SessionLocal()
try:
    logs = db.query(XMLSyncLog).order_by(XMLSyncLog.id.desc()).limit(5).all()
    print(f"Checking last 5 sync logs:")
    for log in logs:
        print(f"- ID: {log.id}, Status: {log.status}, Fetched: {log.products_fetched}, Created: {log.products_created}, Updated: {log.products_updated}, Errors: {log.error_count}")
        if log.error_detail:
            print(f"  Errors: {log.error_detail[:500]}...")
finally:
    db.close()
