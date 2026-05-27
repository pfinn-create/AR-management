from sqlalchemy import Column, Integer, String, Boolean, Numeric, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class CompanySettings(Base):
    __tablename__ = "company_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True)

    # Payment & terms
    payment_terms_days = Column(Integer, default=30)

    # Email preferences
    monitored_inbox = Column(String(255))       # e.g. ar@company.com or personal mailbox
    email_auto_draft = Column(Boolean, default=True)

    # Follow-up sequence — JSON list of day offsets past due date e.g. [1, 7, 14, 30, 45]
    followup_intervals_json = Column(Text, default='[1, 7, 14, 30, 45]')

    # Escalation thresholds
    escalation_days_overdue = Column(Integer, default=60)
    escalation_min_amount = Column(Numeric(15, 2), default=10000)

    # Bank statement format preference for this company
    bank_format = Column(String(10), default="csv")   # "csv" or "pdf"

    company = relationship("Company", backref="settings", uselist=False)
