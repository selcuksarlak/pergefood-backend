import sys
from decimal import Decimal
sys.path.insert(0, '.')
from app.core.database import SessionLocal
from app.models.product import Product

db = SessionLocal()
try:
    products = db.query(Product).all()
    updated = 0
    for p in products:
        needs_update = False
        if p.purchase_price is None:
            p.purchase_price = Decimal("0")
            needs_update = True
        if p.profit_margin_percent is None:
            p.profit_margin_percent = Decimal("35.0")
            needs_update = True
        if p.manual_profit is None:
            p.manual_profit = Decimal("0")
            needs_update = True
        if p.shipping_cost is None:
            p.shipping_cost = Decimal("0")
            needs_update = True
        if p.calculated_sale_price is None:
            p.calculated_sale_price = Decimal("0")
            needs_update = True
            
        if needs_update:
            updated += 1
            
    db.commit()
    print(f"Updated {updated} products with NULL pricing fields.")
finally:
    db.close()
