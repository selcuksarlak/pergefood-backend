from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    res = conn.execute(text("SELECT c.name, t.name as type_name FROM sys.columns c JOIN sys.types t ON c.user_type_id = t.user_type_id WHERE c.object_id = OBJECT_ID('offers')"))
    for row in res:
        print(f"{row.name}: {row.type_name}")
