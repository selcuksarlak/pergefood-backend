from sqlalchemy import create_engine, inspect
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
inspector = inspect(engine)

columns = inspector.get_columns('products')
print("Columns in 'products' table:")
for col in columns:
    print(f"- {col['name']} ({col['type']})")

columns_shipping = inspector.get_columns('shipping_methods')
print("\nColumns in 'shipping_methods' table:")
for col in columns_shipping:
    print(f"- {col['name']} ({col['type']})")
