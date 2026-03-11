import enum
from sqlalchemy import Column, Integer, String, Boolean, Enum
from app.core.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    finance = "finance"
    warehouse = "warehouse"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(150), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.viewer, nullable=False)
    is_active = Column(Boolean, default=True)
