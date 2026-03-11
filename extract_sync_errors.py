
import sys
import json
sys.path.insert(0, '.')
from app.core.database import SessionLocal
from app.models.xml_feed import XMLSyncLog

db = SessionLocal()
try:
    log = db.query(XMLSyncLog).order_by(XMLSyncLog.id.desc()).first()
    if log and log.error_detail:
        errors = json.loads(log.error_detail)
        print(f"Sync ID: {log.id}, Total Errors: {len(errors)}")
        for i, err in enumerate(errors[:10]):
            product = err.get('product', 'Unknown')
            msg = err.get('error', 'No message')
            print(f"{i+1}. Product: {product.encode('ascii', 'replace').decode()} | Error: {msg.encode('ascii', 'replace').decode()}")
    else:
        print(f"No error details for sync ID {log.id if log else 'None'}")
finally:
    db.close()
