from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

COMPANIES = ["CFS", "ASI", "LV", "Dom", "LSD", "TI", "HWA", "H&W", "Com", "I4pro"]


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    default_payment_terms_days = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customers = relationship("Customer", back_populates="company")
    invoices = relationship("Invoice", back_populates="company")
    payments = relationship("Payment", back_populates="company")
    email_threads = relationship("EmailThread", back_populates="company")
    todos = relationship("TodoItem", back_populates="company")
    user_access = relationship("UserCompanyAccess", back_populates="company")
