import sys
sys.path.insert(0, '.')
from sqlalchemy import text
from app.core.database import SessionLocal, engine

print("Altering tables...")
with engine.connect() as conn:
    try:
        # 1. Clear tables
        conn.execute(text("DELETE FROM ai_price_predictions;"))
        conn.execute(text("DELETE FROM market_prices;"))
        conn.execute(text("DELETE FROM product_costs;"))
        conn.execute(text("DELETE FROM xml_product_images;"))
        conn.execute(text("DELETE FROM stock_entries;"))
        conn.execute(text("DELETE FROM stock_outputs;"))
        conn.execute(text("DELETE FROM stock_levels;"))
        conn.execute(text("DELETE FROM stock_sync_item_logs;"))
        conn.execute(text("DELETE FROM stock_sync_logs;"))
        conn.execute(text("DELETE FROM stock_sync_alerts;"))
        conn.execute(text("DELETE FROM products;"))
        print("Tables cleared successfully.")

        # 2. Drop columns (MSSQL syntax can be tricky if there are constraints, but these are just columns)
        try:
            conn.execute(text("ALTER TABLE products DROP COLUMN category;"))
        except Exception as e:
            print(f"Warn (category already dropped?): {e}")
            
        try:
            conn.execute(text("ALTER TABLE products DROP COLUMN brand;"))
        except Exception as e:
            print(f"Warn (brand already dropped?): {e}")

        # 3. Add new foreign keys
        try:
            conn.execute(text("ALTER TABLE products ADD category_id INT NULL;"))
            conn.execute(text("ALTER TABLE products ADD CONSTRAINT FK_Product_Category FOREIGN KEY (category_id) REFERENCES categories(id);"))
        except Exception as e:
            print(f"Warn (category_id already added?): {e}")
            
        try:
            conn.execute(text("ALTER TABLE products ADD brand_id INT NULL;"))
            conn.execute(text("ALTER TABLE products ADD CONSTRAINT FK_Product_Brand FOREIGN KEY (brand_id) REFERENCES brands(id);"))
        except Exception as e:
            print(f"Warn (brand_id already added?): {e}")

        conn.commit()
        print("Schema altered successfully.")
    except Exception as e:
        print("Error altering schema:", e)
