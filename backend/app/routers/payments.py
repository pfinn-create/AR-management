from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
import pandas as pd
import io
from app.database import get_db
from app.models.payment import Payment, RemittanceLine, PaymentStatus, MatchConfidence
from app.models.invoice import Invoice
from app.models.user import User
from app.schemas.payment import PaymentOut, RemittanceApproval, PaymentMatchResult
from app.routers.deps import current_user, assert_company_access

router = APIRouter(prefix="/payments", tags=["payments"])

CHASE_COLUMN_MAP = {
    "Transaction Date": "payment_date",
    "Date": "payment_date",
    "Description": "payer_name",
    "Memo": "memo",
    "Amount": "amount",
    "Credits": "amount",
    "Reference": "reference_number",
    "Check or Slip #": "reference_number",
    "Transaction ID": "bank_transaction_id",
    "Balance": "_ignore",
    "Debit": "_debit",
}


def _parse_amount(val) -> float:
    if pd.isna(val) or val == "":
        return 0.0
    try:
        return abs(float(str(val).replace(",", "").replace("$", "").strip()))
    except Exception:
        return 0.0


def _parse_date(val) -> Optional[datetime]:
    if pd.isna(val) or val == "":
        return None
    try:
        return pd.to_datetime(val).to_pydatetime().replace(tzinfo=timezone.utc)
    except Exception:
        return None


@router.get("", response_model=List[PaymentOut])
def list_payments(
    company_id: int = Query(...),
    status: Optional[PaymentStatus] = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    q = db.query(Payment).filter(Payment.company_id == company_id)
    if status:
        q = q.filter(Payment.status == status)
    payments = q.order_by(Payment.payment_date.desc()).all()
    return payments


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    p = db.query(Payment).filter(Payment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    assert_company_access(user, p.company_id)
    return p


@router.post("/import/chase/{company_id}", response_model=dict)
async def import_chase_csv(
    company_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    content = await file.read()
    try:
        if file.filename.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(content))
        else:
            df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {e}")

    df.rename(columns=CHASE_COLUMN_MAP, inplace=True)
    created = skipped = 0

    for _, row in df.iterrows():
        amt = _parse_amount(row.get("amount", 0))
        debit = _parse_amount(row.get("_debit", 0))
        # Only import credits (incoming payments)
        if amt <= 0 and debit > 0:
            skipped += 1
            continue
        if amt <= 0:
            skipped += 1
            continue

        ref = str(row.get("reference_number", "")).strip() or None
        txn_id = str(row.get("bank_transaction_id", "")).strip() or None

        # Deduplicate by bank_transaction_id or reference
        existing = None
        if txn_id:
            existing = db.query(Payment).filter(
                Payment.company_id == company_id,
                Payment.bank_transaction_id == txn_id,
            ).first()
        if not existing and ref:
            existing = db.query(Payment).filter(
                Payment.company_id == company_id,
                Payment.reference_number == ref,
                Payment.payment_date == _parse_date(row.get("payment_date")),
            ).first()

        if existing:
            skipped += 1
            continue

        p = Payment(
            company_id=company_id,
            payment_date=_parse_date(row.get("payment_date")),
            amount=amt,
            currency="USD",
            payer_name=str(row.get("payer_name", "")).strip() or None,
            reference_number=ref,
            bank_transaction_id=txn_id,
            memo=str(row.get("memo", "")).strip() or None,
            source="chase_upload",
            status=PaymentStatus.pending_review,
        )
        db.add(p)
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped}


@router.post("/{payment_id}/match", response_model=PaymentMatchResult)
async def run_payment_match(
    payment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    p = db.query(Payment).filter(Payment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    assert_company_access(user, p.company_id)

    from app.agents.payment_agent import match_payment
    result = await match_payment(p, db)
    return result


@router.post("/{payment_id}/approve", response_model=PaymentOut)
def approve_remittance(
    payment_id: int,
    req: RemittanceApproval,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    p = db.query(Payment).filter(Payment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    assert_company_access(user, p.company_id)

    lines = db.query(RemittanceLine).filter(
        RemittanceLine.payment_id == payment_id,
        RemittanceLine.id.in_(req.remittance_line_ids),
    ).all()

    for line in lines:
        line.is_approved = req.approved
        line.approved_by = user.id
        line.approved_at = datetime.now(timezone.utc)
        if req.notes:
            line.notes = req.notes

    # Update payment status
    all_lines = db.query(RemittanceLine).filter(RemittanceLine.payment_id == payment_id).all()
    if all_lines and all(l.is_approved for l in all_lines):
        p.status = PaymentStatus.applied
        p.amount_applied = sum(float(l.amount or 0) for l in all_lines)
    elif any(l.is_approved for l in all_lines):
        p.status = PaymentStatus.partially_matched

    db.commit()
    db.refresh(p)
    return p
