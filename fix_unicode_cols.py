from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    print("Altering brands name column to NVARCHAR(255)...")
    try:
        # Drop index first
        conn.execute(text("DROP INDEX ix_brands_name ON brands"))
    except Exception as e:
        print("Index drop failed (maybe doesn't exist):", e)
    
    conn.execute(text("ALTER TABLE brands ALTER COLUMN name NVARCHAR(255) NOT NULL"))
    conn.execute(text("CREATE UNIQUE INDEX ix_brands_name ON brands (name)"))
    print("Brands altered.")

    print("Altering categories name column to NVARCHAR(255)...")
    try:
        # Drop index first
        conn.execute(text("DROP INDEX ix_categories_name ON categories"))
    except Exception as e:
        print("Index drop failed:", e)

    conn.execute(text("ALTER TABLE categories ALTER COLUMN name NVARCHAR(255) NOT NULL"))
    conn.execute(text("CREATE UNIQUE INDEX ix_categories_name ON categories (name)"))
    print("Categories altered.")
    
    conn.commit()
    print("Successfully converted string columns to Unicode (NVARCHAR)")
