from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Enum, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class PaymentStatus(str, enum.Enum):
    pending_review = "pending_review"
    matched = "matched"
    partially_matched = "partially_matched"
    unmatched = "unmatched"
    applied = "applied"


class MatchConfidence(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"
    flagged = "flagged"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    payment_date = Column(DateTime(timezone=True))
    amount = Column(Numeric(15, 2), nullable=False)
    amount_applied = Column(Numeric(15, 2), default=0)
    currency = Column(String(10), default="USD")
    payer_name = Column(String(255))
    reference_number = Column(String(255))
    bank_transaction_id = Column(String(255))
    memo = Column(Text)
    source = Column(String(50))  # "chase_upload" | "remittance_email" | "manual"
    status = Column(Enum(PaymentStatus), default=PaymentStatus.pending_review)
    ai_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="payments")
    remittance_lines = relationship("RemittanceLine", back_populates="payment")


class RemittanceLine(Base):
    __tablename__ = "remittance_lines"

    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    invoice_number_raw = Column(String(100))
    amount = Column(Numeric(15, 2))
    match_confidence = Column(Enum(MatchConfidence), default=MatchConfidence.flagged)
    is_approved = Column(Boolean, default=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payment = relationship("Payment", back_populates="remittance_lines")
    invoice = relationship("Invoice", back_populates="remittance_lines")
