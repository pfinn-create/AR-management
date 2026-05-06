from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CompanyBase(BaseModel):
    code: str
    name: str
    default_payment_terms_days: int = 30


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    default_payment_terms_days: Optional[int] = None
    is_active: Optional[bool] = None


class CompanyOut(CompanyBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CompanySummary(CompanyOut):
    open_invoices_count: int = 0
    total_ar_balance: float = 0.0
    overdue_amount: float = 0.0
    open_todos_count: int = 0
    unanswered_emails_count: int = 0
