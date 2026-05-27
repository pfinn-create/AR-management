from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class EscalationStatus(str, enum.Enum):
    flagged = "flagged"
    under_review = "under_review"
    resolved = "resolved"
    escalated_to_manager = "escalated_to_manager"


class EscalationFlag(Base):
    __tablename__ = "escalation_flags"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    trigger_reason = Column(String(100))   # "days_overdue" | "high_balance" | "both"
    days_overdue = Column(Integer)
    amount_overdue = Column(Numeric(15, 2))
    status = Column(Enum(EscalationStatus), default=EscalationStatus.flagged)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime(timezone=True))
    linked_todo_id = Column(Integer, ForeignKey("todo_items.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    company = relationship("Company")
    customer = relationship("Customer", backref="escalations")
    assigned_to_user = relationship("User", foreign_keys=[assigned_to])
