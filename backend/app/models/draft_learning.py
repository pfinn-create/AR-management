from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class DraftLearning(Base):
    """
    Captures original AI draft vs. user-edited version.
    Used to improve future drafts for the same customer.
    """
    __tablename__ = "draft_learning"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    thread_id = Column(Integer, ForeignKey("email_threads.id"), nullable=True)
    original_subject = Column(Text)
    original_body = Column(Text)
    edited_subject = Column(Text)
    edited_body = Column(Text)
    diff_summary = Column(Text)   # AI-generated plain-language summary of what changed
    edited_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company")
    customer = relationship("Customer", backref="draft_learnings")
    editor = relationship("User", foreign_keys=[edited_by])
