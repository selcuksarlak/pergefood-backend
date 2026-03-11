
import sys
sys.path.insert(0, '.')
from app.core.database import SessionLocal
from app.models.xml_feed import XMLFeedConfig

db = SessionLocal()
try:
    feeds = db.query(XMLFeedConfig).all()
    print(f"Total XML feeds: {len(feeds)}")
    for f in feeds:
        print(f"- ID: {f.id}, Name: {f.name}, URL: {f.url}, Active: {f.is_active}")
finally:
    db.close()
