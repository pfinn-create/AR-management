from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from app.models.payment import PaymentStatus, MatchConfidence


class RemittanceLineOut(BaseModel):
    id: int
    payment_id: int
    invoice_id: Optional[int]
    invoice_number_raw: Optional[str]
    amount: Optional[Decimal]
    match_confidence: MatchConfidence
    is_approved: bool
    notes: Optional[str]

    class Config:
        from_attributes = True


class PaymentOut(BaseModel):
    id: int
    company_id: int
    payment_date: Optional[datetime]
    amount: Decimal
    amount_applied: Decimal
    currency: str
    payer_name: Optional[str]
    reference_number: Optional[str]
    bank_transaction_id: Optional[str]
    memo: Optional[str]
    source: Optional[str]
    status: PaymentStatus
    ai_notes: Optional[str]
    created_at: datetime
    remittance_lines: List[RemittanceLineOut] = []

    class Config:
        from_attributes = True


class RemittanceApproval(BaseModel):
    remittance_line_ids: List[int]
    approved: bool
    notes: Optional[str] = None


class PaymentMatchResult(BaseModel):
    payment_id: int
    lines_matched: int
    lines_flagged: int
    ai_notes: str
