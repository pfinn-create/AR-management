from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime, timezone
import pandas as pd
import io
from app.database import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User
from app.schemas.invoice import InvoiceOut, InvoiceUpdate, InvoiceImportResult
from app.routers.deps import current_user, assert_company_access

router = APIRouter(prefix="/invoices", tags=["invoices"])

NETSUITE_COLUMN_MAP = {
    "Invoice #": "invoice_number",
    "Invoice Number": "invoice_number",
    "PO #": "po_number",
    "PO Number": "po_number",
    "Invoice Date": "invoice_date",
    "Date": "invoice_date",
    "Due Date": "due_date",
    "Amount": "amount",
    "Total": "amount",
    "Amount Paid": "amount_paid",
    "Balance": "balance",
    "Balance Due": "balance",
    "Currency": "currency",
    "Customer": "customer_name",
    "Customer Name": "customer_name",
    "NetSuite ID": "netsuite_id",
    "Internal ID": "netsuite_id",
    "Terms": "payment_terms_days",
    "Payment Terms": "payment_terms_days",
    "Status": "status",
    "Notes": "notes",
    "Memo": "notes",
}

TERMS_MAP = {
    "Net 30": 30, "Net30": 30, "Net 60": 60, "Net60": 60,
    "Net 90": 90, "Net90": 90, "Net 15": 15, "Net15": 15,
    "Due on Receipt": 0,
}


def _parse_terms(val) -> int:
    if pd.isna(val):
        return 30
    if isinstance(val, (int, float)):
        return int(val)
    return TERMS_MAP.get(str(val).strip(), 30)


def _parse_date(val) -> Optional[datetime]:
    if pd.isna(val) or val == "":
        return None
    try:
        return pd.to_datetime(val).to_pydatetime().replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _parse_amount(val) -> float:
    if pd.isna(val) or val == "":
        return 0.0
    try:
        return float(str(val).replace(",", "").replace("$", "").strip())
    except Exception:
        return 0.0


def _map_status(val, balance: float, due_date: Optional[datetime]) -> InvoiceStatus:
    if pd.isna(val) or val == "":
        if balance <= 0:
            return InvoiceStatus.paid
        if due_date and due_date < datetime.now(timezone.utc):
            return InvoiceStatus.overdue
        return InvoiceStatus.open
    s = str(val).lower().strip()
    if s in ("paid", "closed"):
        return InvoiceStatus.paid
    if s in ("overdue", "past due"):
        return InvoiceStatus.overdue
    if s in ("partial", "partially paid"):
        return InvoiceStatus.partial
    if s in ("disputed"):
        return InvoiceStatus.disputed
    return InvoiceStatus.open


@router.get("", response_model=List[InvoiceOut])
def list_invoices(
    company_id: int = Query(...),
    status: Optional[InvoiceStatus] = None,
    customer_id: Optional[int] = None,
    overdue_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    q = db.query(Invoice).filter(Invoice.company_id == company_id)
    if status:
        q = q.filter(Invoice.status == status)
    if customer_id:
        q = q.filter(Invoice.customer_id == customer_id)
    if overdue_only:
        q = q.filter(Invoice.status == InvoiceStatus.overdue)
    invoices = q.order_by(Invoice.due_date.asc()).all()
    result = []
    now = datetime.now(timezone.utc)
    for inv in invoices:
        out = InvoiceOut.model_validate(inv)
        if inv.due_date and inv.status not in (InvoiceStatus.paid, InvoiceStatus.written_off):
            delta = (now - inv.due_date.replace(tzinfo=timezone.utc) if inv.due_date.tzinfo is None else now - inv.due_date)
            out.days_overdue = max(0, delta.days)
        result.append(out)
    return result


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    assert_company_access(user, inv.company_id)
    return inv


@router.patch("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: int,
    req: InvoiceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    assert_company_access(user, inv.company_id)
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(inv, k, v)
    if req.amount_paid is not None:
        inv.balance = inv.amount - inv.amount_paid
    db.commit()
    db.refresh(inv)
    return inv


@router.post("/import/{company_id}", response_model=InvoiceImportResult)
async def import_netsuite_csv(
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

    df.rename(columns=NETSUITE_COLUMN_MAP, inplace=True)
    created = updated = skipped = 0
    errors = []

    for idx, row in df.iterrows():
        try:
            inv_num = str(row.get("invoice_number", "")).strip()
            if not inv_num:
                skipped += 1
                continue

            amount = _parse_amount(row.get("amount", 0))
            amount_paid = _parse_amount(row.get("amount_paid", 0))
            balance_raw = row.get("balance")
            balance = _parse_amount(balance_raw) if not pd.isna(balance_raw) else amount - amount_paid
            due_date = _parse_date(row.get("due_date"))
            status_val = row.get("status")
            status = _map_status(status_val, balance, due_date)

            existing = db.query(Invoice).filter(
                Invoice.company_id == company_id,
                Invoice.invoice_number == inv_num,
            ).first()

            if existing:
                existing.amount = amount
                existing.amount_paid = amount_paid
                existing.balance = balance
                existing.status = status
                existing.due_date = due_date
                existing.invoice_date = _parse_date(row.get("invoice_date"))
                existing.customer_name = str(row.get("customer_name", "")).strip() or existing.customer_name
                existing.notes = str(row.get("notes", "")).strip() or existing.notes
                existing.payment_terms_days = _parse_terms(row.get("payment_terms_days"))
                existing.po_number = str(row.get("po_number", "")).strip() or existing.po_number
                updated += 1
            else:
                inv = Invoice(
                    company_id=company_id,
                    invoice_number=inv_num,
                    po_number=str(row.get("po_number", "")).strip() or None,
                    invoice_date=_parse_date(row.get("invoice_date")),
                    due_date=due_date,
                    amount=amount,
                    amount_paid=amount_paid,
                    balance=balance,
                    currency=str(row.get("currency", "USD")).strip(),
                    payment_terms_days=_parse_terms(row.get("payment_terms_days")),
                    status=status,
                    customer_name=str(row.get("customer_name", "")).strip() or None,
                    netsuite_id=str(row.get("netsuite_id", "")).strip() or None,
                    notes=str(row.get("notes", "")).strip() or None,
                )
                db.add(inv)
                created += 1
        except Exception as e:
            errors.append(f"Row {idx + 2}: {e}")

    db.commit()

    # Auto-generate overdue todos
    _generate_overdue_todos(company_id, db)

    return InvoiceImportResult(created=created, updated=updated, skipped=skipped, errors=errors)


def _generate_overdue_todos(company_id: int, db: Session):
    from app.models.todo import TodoItem, TodoCategory, TodoPriority, TodoStatus
    now = datetime.now(timezone.utc)
    overdue = db.query(Invoice).filter(
        Invoice.company_id == company_id,
        Invoice.status == InvoiceStatus.overdue,
        Invoice.balance > 0,
    ).all()
    for inv in overdue:
        existing = db.query(TodoItem).filter(
            TodoItem.linked_invoice_id == inv.id,
            TodoItem.category == TodoCategory.overdue_invoice,
            TodoItem.status != TodoStatus.done,
        ).first()
        if not existing:
            db.add(TodoItem(
                company_id=company_id,
                category=TodoCategory.overdue_invoice,
                priority=TodoPriority.high,
                title=f"Overdue invoice {inv.invoice_number} — {inv.customer_name} (${float(inv.balance):,.2f})",
                linked_invoice_id=inv.id,
            ))
    db.commit()
