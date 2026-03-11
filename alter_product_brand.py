import sys
sys.path.insert(0, '.')
from sqlalchemy import text
from app.core.database import SessionLocal, engine

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE products ADD brand VARCHAR(100) NULL;"))
        conn.commit()
        print("Column 'brand' added successfully.")
    except Exception as e:
        print("Error adding column (might already exist):", e)
