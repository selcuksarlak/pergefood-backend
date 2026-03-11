from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.xml_service import XMLSyncService
from app.models.xml_feed import XMLFeedConfig

router = APIRouter(prefix="/xml", tags=["XML Sync"])

@router.get("/sync-products")
def sync_products_from_website(db: Session = Depends(get_db)):
    """
    Quick sync products from the hardcoded Pergefood website feed.
    Matches products by Barcode > Code > Name Similarity.
    """
    # 1. Ensure the reference feed config exists
    url = "https://www.pergefood.com/xml.php?custom=OrnekXML"
    config = db.query(XMLFeedConfig).filter(XMLFeedConfig.url.like(f"%{url}%")).first()
    
    if not config:
        config = XMLFeedConfig(
            name="Pergefood Website Feed",
            url=url,
            is_active=True,
            download_images=True,
            image_save_dir="static/product_images",
            item_element="Products",
            field_mapping={
                "Name": "product_name",
                "Product_id": "product_code",
                "Price": "sale_price",
                "Stock": "stock_quantity",
                "Category_Tree": "category",
                "Image1": "image_url",
                "Description": "description"
            }
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    else:
        # Update existing auto-created config if it was wrong
        if config.item_element != "Products":
            config.item_element = "Products"
            config.field_mapping = {
                "Name": "product_name",
                "Product_id": "product_code",
                "Price": "sale_price",
                "Stock": "stock_quantity",
                "Category_Tree": "category",
                "Image1": "image_url",
                "Description": "description"
            }
            db.commit()

    # 2. Run the sync service
    try:
        service = XMLSyncService(db)
        log = service.run_sync(config.id)
        
        return {
            "ProductsAdded": log.products_created,
            "ProductsUpdated": log.products_updated,
            "Errors": log.error_count,
            "SyncID": log.id,
            "SyncDate": log.started_at,
            "Status": log.status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synchronization failed: {str(e)}")
