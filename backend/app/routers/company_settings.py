import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from app.database import get_db
from app.models.company_settings import CompanySettings
from app.models.user import User
from app.routers.deps import current_user, assert_company_access

router = APIRouter(prefix="/settings", tags=["settings"])


class CompanySettingsOut(BaseModel):
    company_id: int
    payment_terms_days: int
    monitored_inbox: Optional[str]
    email_auto_draft: bool
    followup_intervals: List[int]
    escalation_days_overdue: int
    escalation_min_amount: float
    bank_format: str

    class Config:
        from_attributes = True


class CompanySettingsUpdate(BaseModel):
    payment_terms_days: Optional[int] = None
    monitored_inbox: Optional[str] = None
    email_auto_draft: Optional[bool] = None
    followup_intervals: Optional[List[int]] = None
    escalation_days_overdue: Optional[int] = None
    escalation_min_amount: Optional[float] = None
    bank_format: Optional[str] = None


def _to_out(s: CompanySettings) -> CompanySettingsOut:
    return CompanySettingsOut(
        company_id=s.company_id,
        payment_terms_days=s.payment_terms_days or 30,
        monitored_inbox=s.monitored_inbox,
        email_auto_draft=s.email_auto_draft if s.email_auto_draft is not None else True,
        followup_intervals=json.loads(s.followup_intervals_json or "[1,7,14,30,45]"),
        escalation_days_overdue=s.escalation_days_overdue or 60,
        escalation_min_amount=float(s.escalation_min_amount or 10000),
        bank_format=s.bank_format or "csv",
    )


@router.get("/{company_id}", response_model=CompanySettingsOut)
def get_settings(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    s = db.query(CompanySettings).filter(CompanySettings.company_id == company_id).first()
    if not s:
        s = CompanySettings(company_id=company_id)
        db.add(s)
        db.commit()
        db.refresh(s)
    return _to_out(s)


@router.patch("/{company_id}", response_model=CompanySettingsOut)
def update_settings(
    company_id: int,
    req: CompanySettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    s = db.query(CompanySettings).filter(CompanySettings.company_id == company_id).first()
    if not s:
        s = CompanySettings(company_id=company_id)
        db.add(s)
        db.flush()

    if req.payment_terms_days is not None:
        s.payment_terms_days = req.payment_terms_days
    if req.monitored_inbox is not None:
        s.monitored_inbox = req.monitored_inbox
    if req.email_auto_draft is not None:
        s.email_auto_draft = req.email_auto_draft
    if req.followup_intervals is not None:
        s.followup_intervals_json = json.dumps(req.followup_intervals)
    if req.escalation_days_overdue is not None:
        s.escalation_days_overdue = req.escalation_days_overdue
    if req.escalation_min_amount is not None:
        s.escalation_min_amount = Decimal(str(req.escalation_min_amount))
    if req.bank_format is not None:
        s.bank_format = req.bank_format

    db.commit()
    db.refresh(s)
    return _to_out(s)
