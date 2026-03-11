from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    print("Forcibly deleting all categories containing 'Ã' or 'Ä' (Mojibake)...")
    
    # We must explicitly set null to product category_id where category is about to be deleted
    # to avoid Foreign Key constraint failures.
    update_products_sql = """
    UPDATE products 
    SET category_id = NULL 
    WHERE category_id IN (
        SELECT id FROM categories WHERE name LIKE '%Ã%' OR name LIKE '%Ä%' OR name LIKE '%?%'
    )
    """
    
    delete_cats_sql = """
    DELETE FROM categories WHERE name LIKE '%Ã%' OR name LIKE '%Ä%' OR name LIKE '%?%'
    """
    
    res1 = conn.execute(text(update_products_sql))
    print(f"Detached {res1.rowcount} products from bad categories.")
    
    res2 = conn.execute(text(delete_cats_sql))
    print(f"Deleted {res2.rowcount} corrupted categories.")
    
    conn.commit()
    print("Done clearing mojibake.")
