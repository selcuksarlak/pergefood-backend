from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

db = SessionLocal()
user = db.query(User).filter(User.username == 'admin').first()
if user:
    user.hashed_password = get_password_hash('pergefood1234')
    db.commit()
    print("Admin password reset to 'pergefood1234'")
else:
    print("Admin user not found")
db.close()
