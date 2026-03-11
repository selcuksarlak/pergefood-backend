
import sys
sys.path.insert(0, '.')
from app.core.database import SessionLocal
from app.models.product import Product

db = SessionLocal()
try:
    total = db.query(Product).count()
    active = db.query(Product).filter(Product.active_status == True).count()
    inactive = db.query(Product).filter(Product.active_status == False).count()
    print(f"Total: {total}, Active: {active}, Inactive: {inactive}")
finally:
    db.close()
