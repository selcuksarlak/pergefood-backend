from app.core.database import SessionLocal
from app.models.xml_feed import XMLFeedConfig
from app.services.xml_service import XMLSyncService
from app.models.product import Product
from app.models.brand_category import Brand, Category
import requests
import xml.etree.ElementTree as ET

def refresh_all_data():
    db = SessionLocal()
    try:
        # 1. Reset references in Products table to allow deletion
        print("Resetting brand and category references in products...")
        db.query(Product).update({Product.brand_id: None, Product.category_id: None})
        db.commit()

        # 2. Clear Brands and Categories
        print("Clearing existing brands and categories...")
        db.query(Brand).delete()
        db.query(Category).delete()
        db.commit()

        # 3. Sync Brands with fixed encoding logic
        print("Syncing Brands from XML...")
        brand_url = "https://www.pergefood.com/xml.php?custom=MarkaXML"
        res = requests.get(brand_url, timeout=30)
        res.encoding = "windows-1254"
        root = ET.fromstring(res.text)
        unique_brands = {el.text.strip() for el in root.findall('.//mark') if el.text and el.text.strip()}
        for name in unique_brands:
            db.add(Brand(name=name))
        db.commit()
        print(f"Added {len(unique_brands)} brands.")

        # 4. Sync Categories with fixed encoding logic
        print("Syncing Categories from XML...")
        cat_url = "https://www.pergefood.com/xml.php?custom=KategoriXML"
        res = requests.get(cat_url, timeout=30)
        res.encoding = "windows-1254"
        root = ET.fromstring(res.text)
        unique_cats = {el.text.strip() for el in root.findall('.//Category_Tree') if el.text and el.text.strip()}
        for name in unique_cats:
            db.add(Category(name=name))
        db.commit()
        print(f"Added {len(unique_cats)} categories.")

        # 5. Sync Products (this will re-link them and fix product names as well)
        print("Syncing Products from active feeds...")
        sync_service = XMLSyncService(db)
        configs = db.query(XMLFeedConfig).filter(XMLFeedConfig.is_active == True).all()
        for config in configs:
            print(f"Syncing feed: {config.name}")
            log = sync_service.run_sync(config.id)
            print(f"Feed {config.name} synced: {log.products_updated} updated, {log.products_created} created, {log.error_count} errors.")

        print("\nSUCCESS: All data refreshed with correct Turkish character encoding.")

    except Exception as e:
        print(f"FAILURE during refresh: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    refresh_all_data()
