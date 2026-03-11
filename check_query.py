import requests
token = "" # We need a token to test, hmm.. Wait, I can just use python to test the inner function directly or use a script.

# Actually let's use the db to test what the exact SQLAlchemy query generates
import sys
sys.path.insert(0, '.')
from app.core.database import SessionLocal
from app.models.product import Product

db = SessionLocal()
try:
    q1 = db.query(Product).filter(Product.active_status == True).count()
    print(f"Active True count: {q1}")
    
    q2 = db.query(Product).filter(Product.active_status == "1").count()
    print(f"Active '1' count: {q2}")
finally:
    db.close()
