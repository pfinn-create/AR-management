from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone, date
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


@router.delete("/bulk", response_model=dict)
def bulk_delete_payments(
    ids: List[int] = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    payments = db.query(Payment).filter(Payment.id.in_(ids)).all()
    for p in payments:
        assert_company_access(user, p.company_id)
        db.query(RemittanceLine).filter(RemittanceLine.payment_id == p.id).delete()
        db.delete(p)
    db.commit()
    return {"deleted": len(payments)}


@router.delete("/all/{company_id}", response_model=dict)
def delete_all_payments(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    payments = db.query(Payment).filter(Payment.company_id == company_id).all()
    for p in payments:
        db.query(RemittanceLine).filter(RemittanceLine.payment_id == p.id).delete()
        db.delete(p)
    db.commit()
    return {"deleted": len(payments)}


@router.delete("/{payment_id}", response_model=dict)
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    p = db.query(Payment).filter(Payment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    assert_company_access(user, p.company_id)
    db.query(RemittanceLine).filter(RemittanceLine.payment_id == payment_id).delete()
    db.delete(p)
    db.commit()
    return {"deleted": payment_id}


@router.post("/import/chase/{company_id}", response_model=dict)
async def import_chase_csv(
    company_id: int,
    file: UploadFile = File(...),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
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

        pay_date = _parse_date(row.get("payment_date"))
        if from_date and pay_date and pay_date.date() < from_date:
            skipped += 1
            continue
        if to_date and pay_date and pay_date.date() > to_date:
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
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
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

    from app.models.invoice import Invoice
    from app.models.payment import RemittanceLine, MatchConfidence

    created = skipped = auto_matched = 0
    for txn in transactions:
        amt = txn.get("amount", 0)
        if amt <= 0:
            skipped += 1
            continue

        pay_date = txn.get("payment_date")
        if from_date and pay_date and pay_date.date() < from_date:
            skipped += 1
            continue
        if to_date and pay_date and pay_date.date() > to_date:
            skipped += 1
            continue

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
            reference_number=txn.get("reference_number"),
            memo=txn.get("memo"),
            source="chase_pdf",
            status=PaymentStatus.pending_review,
        )
        db.add(p)
        db.flush()

        # Auto-create remittance lines from embedded invoice references
        inv_refs = txn.get("invoice_refs", [])
        for inv_num in inv_refs:
            inv = db.query(Invoice).filter(
                Invoice.company_id == company_id,
                Invoice.invoice_number == inv_num,
            ).first()
            line = RemittanceLine(
                payment_id=p.id,
                invoice_id=inv.id if inv else None,
                invoice_number_raw=inv_num,
                amount=amt if len(inv_refs) == 1 else None,
                match_confidence=MatchConfidence.high if inv else MatchConfidence.medium,
                notes="Auto-matched from bank remittance data" if inv else "Invoice not found in system",
            )
            db.add(line)
            if inv:
                auto_matched += 1

        if inv_refs:
            p.status = PaymentStatus.matched if any(
                db.query(Invoice).filter(Invoice.company_id == company_id, Invoice.invoice_number == r).first()
                for r in inv_refs
            ) else PaymentStatus.pending_review

        created += 1

    db.commit()
    return {"created": created, "skipped": skipped, "total_parsed": len(transactions), "auto_matched": auto_matched}


def _parse_chase_pdf(content: bytes) -> list[dict]:
    """
    Parse a JPMorgan Chase Balance and Transaction Report PDF.
    Extracts credit transactions and remittance data (invoice references).
    """
    import pdfplumber
    from dateutil.parser import parse as dateparse

    txn_simple = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(.+)")
    amount_re = re.compile(r"([\d,]+\.\d{2})")
    inv_ref_re = re.compile(r"RMR\*IV\*([A-Za-z0-9\-]+)")
    # ACH field patterns — present in main line or continuation lines
    orig_name_re = re.compile(r"ORIG CO NAME:\s*([^|]+?)(?=\s+(?:ORIG ID|DESC DATE|ENTRY DESCR|TRACE|IND ID|IND NAME|REMARK|$))")
    ind_name_re  = re.compile(r"IND NAME:\s*([^|]+?)(?=\s+(?:ORIG ID|DESC DATE|ENTRY DESCR|TRACE|IND ID|REMARK|$))")
    nte_name_re  = re.compile(r"NTE\*ZZZ\*([^|\\]+)")  # full legal name from EDI note

    # Skip these — they are debits or internal transfers, not customer receipts
    DEBIT_KEYWORDS = [
        "DEBIT", " DB ", "DRAWDOWN", "CASH CNTRN", "ACH SETTLEMENT",
        "FPRS", "PRFUND", "CONCENTRATION", "FOREIGN EXCHANGE",
        "EXCHANGE DEB", "WIRE DEBIT", "BOOK TRANSFER DB",
    ]

    all_text = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            all_text.append(text)

    lines = "\n".join(all_text).split("\n")

    transactions = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        m = txn_simple.match(line)
        if m:
            tran_date_str = m.group(1)
            description = m.group(3).strip()
            desc_upper = description.upper()

            if any(kw in desc_upper for kw in DEBIT_KEYWORDS):
                i += 1
                continue

            # Collect continuation lines
            j = i + 1
            detail_lines = []
            while j < len(lines):
                nxt = lines[j].strip()
                if txn_simple.match(nxt) or nxt.startswith("Balance and Transaction"):
                    break
                if nxt:
                    detail_lines.append(nxt)
                j += 1

            detail_block = " ".join(detail_lines)
            # Search both the main line and continuation lines for all patterns
            full_block = description + " " + detail_block

            # Extract amounts — credit is second-to-last number, balance is last
            amounts = [float(a.replace(",", "")) for a in amount_re.findall(line)]
            if not amounts:
                i = j
                continue
            credit_amount = amounts[-2] if len(amounts) >= 2 else amounts[0]
            if credit_amount <= 0:
                i = j
                continue

            # Payer name: prefer NTE (full legal name) > ORIG CO NAME > IND NAME > truncated description
            payer = None
            nte = nte_name_re.search(full_block)
            orig = orig_name_re.search(full_block)
            ind  = ind_name_re.search(full_block)
            if nte:
                payer = nte.group(1).strip()[:255]
            elif orig:
                payer = orig.group(1).strip()[:255]
            elif ind:
                payer = ind.group(1).strip()[:255]

            # Fallback: first meaningful word token before any ORIG ID / IND / ENTRY field
            if not payer:
                clean = re.split(r'\s+ORIG\s+ID|\s+IND\s+|\s+ENTRY\s+|\s+TRACE\s+', description)[0]
                payer = clean.strip()[:120] or description[:120]

            # Invoice refs from remittance data (anywhere in full block)
            inv_refs = inv_ref_re.findall(full_block)

            try:
                pay_date = dateparse(tran_date_str).replace(tzinfo=timezone.utc)
            except Exception:
                pay_date = None

            transactions.append({
                "payment_date": pay_date,
                "payer_name": payer,
                "amount": credit_amount,
                "reference_number": None,
                "memo": description[:500],
                "invoice_refs": inv_refs,
            })

            i = j
            continue

        i += 1

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
