from app.core.database import SessionLocal
from app.models.product import Product
from app.models.brand_category import Brand, Category

def check_data():
    db = SessionLocal()
    try:
        print("Checking Brands:")
        brands = db.query(Brand).limit(5).all()
        for b in brands:
            print(f"- {b.name}")
            
        print("\nChecking Categories:")
        cats = db.query(Category).limit(5).all()
        for c in cats:
            print(f"- {c.name}")
            
        print("\nChecking Products:")
        products = db.query(Product).filter(Product.brand_id.isnot(None)).limit(5).all()
        for p in products:
            print(f"- {p.product_name} (Brand: {p.brand.name if p.brand else 'N/A'}, Cat: {p.category.name if p.category else 'N/A'})")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_data()
