from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class TodoCategory(str, enum.Enum):
    unanswered_email = "unanswered_email"
    missing_invoice_detail = "missing_invoice_detail"
    payment_review = "payment_review"
    draft_approval = "draft_approval"
    overdue_invoice = "overdue_invoice"
    general = "general"


class TodoPriority(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class TodoStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    done = "done"
    snoozed = "snoozed"


class TodoItem(Base):
    __tablename__ = "todo_items"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    category = Column(Enum(TodoCategory), nullable=False)
    priority = Column(Enum(TodoPriority), default=TodoPriority.medium)
    status = Column(Enum(TodoStatus), default=TodoStatus.open)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    due_date = Column(DateTime(timezone=True))

    # Polymorphic links
    linked_invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    linked_thread_id = Column(Integer, ForeignKey("email_threads.id"), nullable=True)
    linked_payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)

    is_auto_generated = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    company = relationship("Company", back_populates="todos")
    assigned_to_user = relationship("User", back_populates="todos", foreign_keys=[assigned_to])
