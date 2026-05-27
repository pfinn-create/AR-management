from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class DisputeStatus(str, enum.Enum):
    open = "open"
    under_review = "under_review"
    resolved = "resolved"
    rejected = "rejected"


class DisputeReason(str, enum.Enum):
    incorrect_amount = "incorrect_amount"
    duplicate_invoice = "duplicate_invoice"
    goods_not_received = "goods_not_received"
    quality_issue = "quality_issue"
    already_paid = "already_paid"
    contract_dispute = "contract_dispute"
    other = "other"


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    reason = Column(Enum(DisputeReason), nullable=False)
    description = Column(Text)
    status = Column(Enum(DisputeStatus), default=DisputeStatus.open)
    raised_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime(timezone=True))
    linked_thread_id = Column(Integer, ForeignKey("email_threads.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    company = relationship("Company")
    invoice = relationship("Invoice", backref="disputes")
    customer = relationship("Customer")
    raised_by_user = relationship("User", foreign_keys=[raised_by])
    assigned_to_user = relationship("User", foreign_keys=[assigned_to])
