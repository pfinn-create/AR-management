from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    provider = Column(String(20), nullable=False)  # "gmail"
    mailbox = Column(String(255), nullable=False)   # email address
    access_token = Column(Text)
    refresh_token = Column(Text, nullable=False)
    token_expiry = Column(DateTime(timezone=True))
    scopes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "provider", "mailbox", name="uq_oauth_company_provider_mailbox"),
    )

    company = relationship("Company")
