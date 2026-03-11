from app.core.database import SessionLocal
from app.models.user import User

db = SessionLocal()
users = db.query(User).all()
print(f"Total users: {len(users)}")
for u in users:
    print(f"Username: '{u.username}', Email: '{u.email}', Role: '{u.role}', IsActive: {u.is_active}")

db.close()
