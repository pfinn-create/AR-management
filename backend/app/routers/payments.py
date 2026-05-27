from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
import pandas as pd
import io
import re
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

    # Trigger payment matching agent for all new payments
    from app.agents.coordinator import trigger_for_company
    import asyncio
    asyncio.create_task(trigger_for_company(company_id, ["reply_tracking"]))

    return {"created": created, "skipped": skipped}


@router.post("/import/chase-pdf/{company_id}", response_model=dict)
async def import_chase_pdf(
    company_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Parse a Chase bank statement PDF and extract credit transactions."""
    assert_company_access(user, company_id)

    try:
        import pdfplumber
    except ImportError:
        raise HTTPException(status_code=500, detail="pdfplumber not installed")

    content = await file.read()
    transactions = _parse_chase_pdf(content)

    created = skipped = 0
    for txn in transactions:
        amt = txn.get("amount", 0)
        if amt <= 0:
            skipped += 1
            continue

        ref = txn.get("reference_number") or None
        pay_date = txn.get("payment_date")

        existing = db.query(Payment).filter(
            Payment.company_id == company_id,
            Payment.payer_name == txn.get("payer_name"),
            Payment.amount == amt,
            Payment.payment_date == pay_date,
        ).first()

        if existing:
            skipped += 1
            continue

        p = Payment(
            company_id=company_id,
            payment_date=pay_date,
            amount=amt,
            currency="USD",
            payer_name=txn.get("payer_name"),
            reference_number=ref,
            memo=txn.get("memo"),
            source="chase_pdf",
            status=PaymentStatus.pending_review,
        )
        db.add(p)
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped, "total_parsed": len(transactions)}


def _parse_chase_pdf(content: bytes) -> list[dict]:
    """
    Extract credit transactions from a Chase PDF statement or transaction export.
    Handles both the full monthly statement layout and the filtered transaction export.
    """
    import pdfplumber

    transactions = []
    date_pattern = re.compile(r"(\d{2}/\d{2})")
    amount_pattern = re.compile(r"\$([\d,]+\.\d{2})")

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")

            for i, line in enumerate(lines):
                # Look for lines with a date at the start and a positive dollar amount
                date_match = date_pattern.match(line.strip())
                if not date_match:
                    continue

                # Try to extract amount — credits appear as positive in Chase exports
                amounts = amount_pattern.findall(line)
                if not amounts:
                    continue

                amount_str = amounts[-1].replace(",", "")
                try:
                    amount = float(amount_str)
                except ValueError:
                    continue

                # Skip if this looks like a debit (negative context clue words)
                line_lower = line.lower()
                if any(kw in line_lower for kw in ["purchase", "payment to", "atm", "fee", "interest"]):
                    continue

                # Extract description (everything between date and amount)
                desc = re.sub(r"\d{2}/\d{2}", "", line)
                desc = amount_pattern.sub("", desc).strip()
                desc = re.sub(r"\s+", " ", desc).strip()

                # Try to parse the date (Chase uses MM/DD format — assume current year)
                try:
                    from dateutil.parser import parse as dateparse
                    pay_date = dateparse(date_match.group(1)).replace(
                        year=datetime.now().year, tzinfo=timezone.utc
                    )
                except Exception:
                    pay_date = None

                transactions.append({
                    "payment_date": pay_date,
                    "payer_name": desc[:255] if desc else "Chase PDF Import",
                    "amount": amount,
                    "memo": f"PDF import: {line.strip()[:200]}",
                    "reference_number": None,
                })

    return transactions


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
