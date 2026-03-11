"""
MSSQL Connection Test + Table Creation
"""
import sys
sys.path.insert(0, '.')

from app.core.config import settings
from app.core.database import engine, Base
import app.models  # noqa - register all models

print(f"Database URL: {settings.DATABASE_URL[:60]}...")
print("Connecting to MSSQL...")

try:
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("SELECT @@VERSION"))
        version = result.fetchone()[0]
        print(f"[OK] Connected! SQL Server: {version[:80]}")

    print("\nCreating tables if they don't exist...")
    Base.metadata.create_all(bind=engine)
    print("[OK] All tables created/verified successfully!")

except Exception as e:
    print(f"[ERROR] Connection failed: {e}")
    sys.exit(1)
