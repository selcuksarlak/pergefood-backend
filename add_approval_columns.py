from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, isolation_level="AUTOCOMMIT")
with engine.connect() as conn:
    print("Altering offers table to add approved_at and is_notification_read...")
    try:
        conn.execute(text("ALTER TABLE offers ADD approved_at DATETIMEOFFSET NULL"))
        print("Success adding approved_at")
    except Exception as e:
        print(f"Error adding approved_at (might already exist): {e}")

    try:
        conn.execute(text("ALTER TABLE offers ADD is_notification_read BIT NOT NULL DEFAULT 0"))
        print("Success adding is_notification_read")
    except Exception as e:
        print(f"Error adding is_notification_read (might already exist): {e}")
        
    try:
        conn.execute(text("UPDATE offers SET is_notification_read = 1 WHERE status = 'onaylandi'"))
        print("Success updating legacy approved offers as read")
    except Exception as e:
        print(f"Error marking legacy read: {e}")

    print("Migration finished securely.")
