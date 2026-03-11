from app.core.database import SessionLocal
from app.models.xml_feed import XMLSyncLog
import json

db = SessionLocal()
last_log = db.query(XMLSyncLog).order_by(XMLSyncLog.id.desc()).first()
if last_log:
    print(f"Log ID: {last_log.id}")
    print(f"Status: {last_log.status}")
    print(f"Error Count: {last_log.error_count}")
    if last_log.error_detail:
        errors = json.loads(last_log.error_detail)
        for i, err in enumerate(errors[:10]):
            print(f"Error {i+1}: {err}")
else:
    print("No logs found")
db.close()
