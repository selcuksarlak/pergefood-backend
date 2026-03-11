from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)

alter_products = [
    "ALTER TABLE products ADD purchase_price NUMERIC(10, 4) DEFAULT 0",
    "ALTER TABLE products ADD profit_margin_percent NUMERIC(5, 2) DEFAULT 35.0",
    "ALTER TABLE products ADD manual_profit NUMERIC(10, 4) DEFAULT 0",
    "ALTER TABLE products ADD shipping_cost NUMERIC(10, 4) DEFAULT 0",
    "ALTER TABLE products ADD calculated_sale_price NUMERIC(10, 4) DEFAULT 0"
]

alter_shipping = [
    "ALTER TABLE shipping_methods ADD min_order_amount NUMERIC(10, 2) DEFAULT 0",
    "ALTER TABLE shipping_methods ADD max_desi FLOAT DEFAULT 0",
    "ALTER TABLE shipping_methods ADD desi_price NUMERIC(10, 2) DEFAULT 0"
]

with engine.connect() as conn:
    print("Updating 'products' table...")
    for sql in alter_products:
        try:
            conn.execute(text(sql))
            conn.commit()
            print(f"Executed: {sql}")
        except Exception as e:
            print(f"Error (probably already exists): {e}")

    print("\nUpdating 'shipping_methods' table...")
    for sql in alter_shipping:
        try:
            conn.execute(text(sql))
            conn.commit()
            print(f"Executed: {sql}")
        except Exception as e:
            print(f"Error (probably already exists): {e}")

print("\nSchema update complete.")
