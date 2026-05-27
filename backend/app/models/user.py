from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class UserRole(str, enum.Enum):
    ar_manager = "ar_manager"
    ar_specialist = "ar_specialist"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.ar_specialist)
    is_active = Column(Boolean, default=True)
    # Email consent — asked once on first login
    email_consent = Column(Boolean, default=False)
    email_consent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company_access = relationship("UserCompanyAccess", back_populates="user")
    todos = relationship("TodoItem", back_populates="assigned_to_user", foreign_keys="TodoItem.assigned_to")


class UserCompanyAccess(Base):
    __tablename__ = "user_company_access"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    user = relationship("User", back_populates="company_access")
    company = relationship("Company", back_populates="user_access")
