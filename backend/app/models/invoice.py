from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class InvoiceStatus(str, enum.Enum):
    open = "open"
    partial = "partial"
    paid = "paid"
    overdue = "overdue"
    disputed = "disputed"
    written_off = "written_off"


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    invoice_number = Column(String(100), nullable=False)
    po_number = Column(String(100))
    invoice_date = Column(DateTime(timezone=True))
    due_date = Column(DateTime(timezone=True))
    amount = Column(Numeric(15, 2), nullable=False, default=0)
    amount_paid = Column(Numeric(15, 2), default=0)
    balance = Column(Numeric(15, 2), default=0)
    currency = Column(String(10), default="USD")
    payment_terms_days = Column(Integer, default=30)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.open)
    customer_name = Column(String(255))
    notes = Column(Text)
    netsuite_id = Column(String(100))
    imported_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    company = relationship("Company", back_populates="invoices")
    customer = relationship("Customer", back_populates="invoices")
    remittance_lines = relationship("RemittanceLine", back_populates="invoice")
