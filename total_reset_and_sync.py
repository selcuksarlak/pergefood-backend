from app.core.database import SessionLocal, engine
from sqlalchemy import text
from app.models.xml_feed import XMLFeedConfig
from app.services.xml_service import XMLSyncService
import requests
import xml.etree.ElementTree as ET
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def wipe_and_resync():
    db = SessionLocal()
    try:
        print("--- PHASE 1: WIPING DATABASE ---")
        tables_to_wipe = [
            "ai_price_predictions",
            "market_prices",
            "stock_sync_alerts",
            "stock_sync_item_logs",
            "offer_items",
            "offers",
            "stock_outputs",
            "stock_entries",
            "invoice_items",
            "invoices",
            "suppliers",
            "xml_product_images",
            "product_costs",  # Added this
            "stock_levels",    # Added this too
            "products",
            "brands",
            "categories"
        ]
        
        with engine.connect() as conn:
            for table in tables_to_wipe:
                print(f"Wiping table: {table}")
                conn.execute(text(f"DELETE FROM {table}"))
            conn.commit()
        
        print("\n--- PHASE 2: RE-SYNCING BRANDS & CATEGORIES (UTF-8) ---")
        
        # Brands
        brand_url = "https://www.pergefood.com/xml.php?custom=MarkaXML"
        res = requests.get(brand_url, timeout=30)
        res.encoding = "utf-8"
        root = ET.fromstring(res.text)
        unique_brands = {el.text.strip() for el in root.findall('.//mark') if el.text and el.text.strip()}
        
        with engine.connect() as conn:
            for name in unique_brands:
                conn.execute(text("INSERT INTO brands (name, created_at) VALUES (:n, GETDATE())"), {"n": name})
            
            # Categories
            cat_url = "https://www.pergefood.com/xml.php?custom=KategoriXML"
            res = requests.get(cat_url, timeout=30)
            res.encoding = "utf-8"
            root = ET.fromstring(res.text)
            unique_cats = {el.text.strip() for el in root.findall('.//Category_Tree') if el.text and el.text.strip()}
            for name in unique_cats:
                conn.execute(text("INSERT INTO categories (name, created_at) VALUES (:n, GETDATE())"), {"n": name})
            conn.commit()
            
        print(f"Added {len(unique_brands)} brands and {len(unique_cats)} categories.")

        print("\n--- PHASE 3: RE-SYNCING PRODUCTS (UTF-8) ---")
        sync_service = XMLSyncService(db)
        configs = db.query(XMLFeedConfig).filter(XMLFeedConfig.is_active == True).all()
        for config in configs:
            print(f"Syncing feed: {config.name}")
            log = sync_service.run_sync(config.id)
            print(f"Feed {config.name} results: {log.products_created} created, {log.products_updated} updated, {log.error_count} errors.")
        
        db.commit()
        print("\n--- PHASE 4: RE-SYNCING STOCK POSITIONS ---")
        # In this simplistic reset, we reset current_stock to values from XML.
        # Since products were recreated, XMLSyncService handled StockLevel creation inside _upsert_product.
        
        print("\nSUCCESS: Database wiped and re-synced with correct UTF-8 encoding.")

    except Exception as e:
        print(f"FAILURE: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    wipe_and_resync()
