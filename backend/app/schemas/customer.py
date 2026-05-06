from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from decimal import Decimal


class CustomerBase(BaseModel):
    customer_code: Optional[str] = None
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    payment_terms_days: int = 30
    credit_limit: Optional[Decimal] = None


class CustomerCreate(CustomerBase):
    company_id: int


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    payment_terms_days: Optional[int] = None
    credit_limit: Optional[Decimal] = None
    is_active: Optional[bool] = None


class CustomerOut(CustomerBase):
    id: int
    company_id: int
    is_active: bool
    created_at: datetime
    open_balance: Optional[float] = None
    overdue_balance: Optional[float] = None

    class Config:
        from_attributes = True


class CustomerImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str] = []
