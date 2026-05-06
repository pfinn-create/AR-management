from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class ThreadStatus(str, enum.Enum):
    unread = "unread"
    needs_response = "needs_response"
    draft_ready = "draft_ready"
    responded = "responded"
    closed = "closed"


class EmailSource(str, enum.Enum):
    gmail = "gmail"
    outlook = "outlook"


class EmailThread(Base):
    __tablename__ = "email_threads"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    external_thread_id = Column(String(500))
    subject = Column(String(500))
    source = Column(Enum(EmailSource))
    mailbox = Column(String(255))
    status = Column(Enum(ThreadStatus), default=ThreadStatus.unread)
    last_message_at = Column(DateTime(timezone=True))
    snippet = Column(Text)
    linked_invoice_numbers = Column(Text)  # comma-separated
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    company = relationship("Company", back_populates="email_threads")
    customer = relationship("Customer", back_populates="email_threads")
    messages = relationship("EmailMessage", back_populates="thread", order_by="EmailMessage.received_at")


class EmailMessage(Base):
    __tablename__ = "email_messages"

    id = Column(Integer, primary_key=True)
    thread_id = Column(Integer, ForeignKey("email_threads.id"), nullable=False)
    external_message_id = Column(String(500))
    sender = Column(String(255))
    recipient = Column(Text)
    body_text = Column(Text)
    body_html = Column(Text)
    received_at = Column(DateTime(timezone=True))
    is_draft = Column(Boolean, default=False)
    is_outbound = Column(Boolean, default=False)
    draft_external_id = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    thread = relationship("EmailThread", back_populates="messages")
