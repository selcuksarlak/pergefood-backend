from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    print("Altering customer_name to NVARCHAR(200)...")
    try:
        conn.execute(text("ALTER TABLE offers ALTER COLUMN customer_name NVARCHAR(200) NOT NULL"))
        print("Success for offers.customer_name")
    except Exception as e:
        print(f"Error offers: {e}")
        
    print("Altering products.product_name to NVARCHAR(200)...")
    try:
        # We might need to drop indexes if product_name is indexed, but let's try
        conn.execute(text("ALTER TABLE products ALTER COLUMN product_name NVARCHAR(200) NOT NULL"))
        print("Success for products.product_name")
    except Exception as e:
        # Check if indexing prevents altering:
        print(f"Failed to alter products.product_name (maybe index lock): {e}")
        
    conn.commit()
    print("Database unicode conversions finished.")
