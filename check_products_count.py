
import sys
sys.path.insert(0, '.')
from app.core.database import SessionLocal
from app.models.product import Product

db = SessionLocal()
try:
    count = db.query(Product).count()
    print(f"Total products in database: {count}")
    if count > 0:
        products = db.query(Product).limit(5).all()
        for p in products:
            print(f"- {p.product_code}: {p.product_name}")
finally:
    db.close()
