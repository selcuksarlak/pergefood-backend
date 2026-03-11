from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    print("Checking if status column exists in offers table...")
    # Add status
    try:
        conn.execute(text("ALTER TABLE offers ADD status NVARCHAR(50) NOT NULL DEFAULT 'bekliyor'"))
        print("Added 'status' column to offers.")
    except Exception as e:
        print(f"Status column may already exist: {e}")
        
    # Add public_token
    try:
        conn.execute(text("ALTER TABLE offers ADD public_token NVARCHAR(64) NULL"))
        print("Added 'public_token' column to offers.")
    except Exception as e:
        print(f"Public token column may already exist: {e}")
        
    # Add index for public_token
    try:
        conn.execute(text("CREATE UNIQUE INDEX ix_offers_public_token ON offers (public_token) WHERE public_token IS NOT NULL"))
        print("Created index for public_token.")
    except Exception as e:
        print(f"Public token index may already exist: {e}")
        
    conn.commit()
    print("Online Offer columns applied successfully.")
