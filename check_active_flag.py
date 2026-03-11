import sys
sys.path.insert(0, '.')
from app.core.database import SessionLocal
from app.models.product import Product

db = SessionLocal()
try:
    total = db.query(Product).count()
    active = db.query(Product).filter(Product.active_status == True).count()
    inactive = db.query(Product).filter(Product.active_status == False).count()
    Null_status = db.query(Product).filter(Product.active_status.is_(None)).count()
    
    print(f"Total: {total}")
    print(f"Active: {active}")
    print(f"Inactive: {inactive}")
    print(f"NULL Status: {Null_status}")
    
    if inactive > 0:
        db.query(Product).filter(Product.active_status == False).update({"active_status": True})
        db.commit()
        print(f"Updated {inactive} inactive products to active.")
    if Null_status > 0:
        db.query(Product).filter(Product.active_status.is_(None)).update({"active_status": True})
        db.commit()
        print(f"Updated {Null_status} NULL products to active.")
        
finally:
    db.close()
