from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from app.models.invoice import InvoiceStatus


class InvoiceBase(BaseModel):
    invoice_number: str
    po_number: Optional[str] = None
    invoice_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    amount: Decimal
    currency: str = "USD"
    payment_terms_days: int = 30
    customer_name: Optional[str] = None
    notes: Optional[str] = None


class InvoiceCreate(InvoiceBase):
    company_id: int
    customer_id: Optional[int] = None


class InvoiceUpdate(BaseModel):
    status: Optional[InvoiceStatus] = None
    amount_paid: Optional[Decimal] = None
    notes: Optional[str] = None
    customer_id: Optional[int] = None


class InvoiceOut(InvoiceBase):
    id: int
    company_id: int
    customer_id: Optional[int]
    amount_paid: Decimal
    balance: Decimal
    status: InvoiceStatus
    netsuite_id: Optional[str]
    imported_at: datetime
    days_overdue: Optional[int] = None

    class Config:
        from_attributes = True


class InvoiceImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: List[str] = []
    columns_found: List[str] = []
