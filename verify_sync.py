from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.stock_xml_service import StockXMLSyncService
from app.services.xml_service import XMLSyncService # The 111 errors were in XMLSyncLog, likely from this service
from app.core.config import settings
from app.models.xml_feed import XMLFeedConfig

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# Try to find a config to run
config = db.query(XMLFeedConfig).first()
if config:
    print(f"Running sync for feed: {config.name}")
    # We need to see how XMLSyncService is called.
    # Looking at the file list, there is xml_service.py
    from app.services.xml_service import XMLSyncService
    svc = XMLSyncService(db)
    log = svc.run_sync(config.id)
    print(f"Sync Result: {log.status}")
    print(f"Fetched: {log.products_fetched}")
    print(f"Updated: {log.products_updated}")
    print(f"Errors: {log.error_count}")
    if log.error_detail:
        print(f"Errors: {log.error_detail[:500]}")
else:
    print("No XML feed config found to test.")

db.close()
