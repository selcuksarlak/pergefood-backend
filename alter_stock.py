from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
with engine.begin() as conn:
    try:
        conn.execute(text("ALTER TABLE stock_entries ADD invoice_number VARCHAR(100) NULL;"))
        print("Added invoice_number")
    except Exception as e:
        print("Error adding invoice_number:", e)
        
    try:
        conn.execute(text("ALTER TABLE stock_entries ADD invoice_date DATETIME NULL;"))
        print("Added invoice_date")
    except Exception as e:
        print("Error adding invoice_date:", e)
        
    try:
        conn.execute(text("ALTER TABLE stock_entries ADD supplier_name VARCHAR(200) NULL;"))
        print("Added supplier_name")
    except Exception as e:
        print("Error adding supplier_name:", e)

print("Migration completed")
