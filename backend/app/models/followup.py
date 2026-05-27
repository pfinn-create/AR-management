from sqlalchemy import Column, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class FollowUpLog(Base):
    """Tracks which follow-up sequence stage each customer/invoice is at."""
    __tablename__ = "followup_logs"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    sequence_stage = Column(Integer, nullable=False)          # 1 = first interval, 2 = second, etc.
    days_overdue_at_trigger = Column(Integer)
    todo_id = Column(Integer, ForeignKey("todo_items.id"), nullable=True)
    thread_id = Column(Integer, ForeignKey("email_threads.id"), nullable=True)
    was_replied_to = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company")
    customer = relationship("Customer", backref="followup_logs")
    invoice = relationship("Invoice", backref="followup_logs")
