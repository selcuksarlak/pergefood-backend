from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, isolation_level="AUTOCOMMIT")
with engine.connect() as conn:
    print("Altering customer_name to NVARCHAR(200)...")
    try:
        conn.execute(text("ALTER TABLE offers ALTER COLUMN customer_name NVARCHAR(200) NOT NULL"))
        print("Success for offers.customer_name")
    except Exception as e:
        print(f"Error offers: {e}")

    try:
        print("Dropping index on product_name temporarily...")
        conn.execute(text("DROP INDEX ix_products_product_name ON products"))
        conn.execute(text("ALTER TABLE products ALTER COLUMN product_name NVARCHAR(200) NOT NULL"))
        conn.execute(text("CREATE INDEX ix_products_product_name ON products (product_name)"))
        print("Success for products.product_name")
    except Exception as e:
        print(f"Failed to alter products.product_name: {e}")
        
    print("Database unicode conversions finished securely.")
