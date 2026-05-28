from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime, timezone
import pandas as pd
import io
import xml.etree.ElementTree as ET
from app.database import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User
from app.schemas.invoice import InvoiceOut, InvoiceUpdate, InvoiceImportResult
from app.routers.deps import current_user, assert_company_access


def _parse_netsuite_xml(content: bytes) -> pd.DataFrame:
    """Parse NetSuite SpreadsheetML XML exports (.xls files that are actually XML).
    Handles grouped customer header rows where the customer name appears once
    before a block of invoice rows."""
    text = content.decode("utf-8", errors="replace")
    # Strip namespace for easier parsing
    text = text.replace(' xmlns="urn:schemas-microsoft-com:office:spreadsheet"', '')
    text = text.replace('ss:', '')
    root = ET.fromstring(text)

    worksheet = root.find('.//Worksheet')
    if worksheet is None:
        return pd.DataFrame()
    table = worksheet.find('Table')
    if table is None:
        return pd.DataFrame()

    # Collect all rows as lists of cell values
    all_rows = []
    for row in table.findall('Row'):
        cells = []
        col_idx = 0
        for cell in row.findall('Cell'):
            # Handle ss:Index for sparse rows
            idx_attr = cell.get('Index')
            if idx_attr:
                target = int(idx_attr) - 1
                while col_idx < target:
                    cells.append(None)
                    col_idx += 1
            data = cell.find('Data')
            cells.append(data.text if data is not None else None)
            col_idx += 1
        all_rows.append(cells)

    # Find the header row (contains "Document Number" or "Invoice #")
    header_idx = None
    for i, row in enumerate(all_rows):
        row_vals = [str(v).strip() if v else "" for v in row]
        if any(v in ("Document Number", "Invoice #", "Invoice Number") for v in row_vals):
            header_idx = i
            break

    if header_idx is None:
        return pd.DataFrame()

    headers = [str(v).strip() if v else f"col_{i}" for i, v in enumerate(all_rows[header_idx])]
    n_cols = len(headers)

    # Build records — customer name appears as a single-cell row before its invoices
    records = []
    current_customer = None
    for row in all_rows[header_idx + 1:]:
        if not row or all(v is None or str(v).strip() == "" for v in row):
            continue
        non_empty = [v for v in row if v is not None and str(v).strip() != ""]
        # Customer header row: single non-empty cell, not "Total", not a date/number
        if len(non_empty) == 1:
            val = str(non_empty[0]).strip()
            if not val.startswith("Total") and not val.replace(".", "").replace("-", "").isdigit():
                current_customer = val
            continue
        # Pad row to header length
        padded = list(row) + [None] * (n_cols - len(row))
        rec = {headers[i]: padded[i] for i in range(n_cols)}
        if current_customer and "Customer:Project" in headers:
            rec["Customer:Project"] = current_customer
        records.append(rec)

    return pd.DataFrame(records)


def _normalize_grouped_df(df: pd.DataFrame) -> pd.DataFrame:
    """Handle NetSuite grouped xlsx exports where customer name appears in its own row
    with NaN in all other columns, followed by invoice rows with NaN in the customer column."""
    customer_col = next((c for c in df.columns if "customer" in c.lower() or c == "Customer:Project"), None)
    doc_col = next((c for c in df.columns if "document" in c.lower() or "invoice" in c.lower()), None)
    if customer_col is None or doc_col is None:
        return df

    # Forward-fill customer name from grouped header rows into invoice rows
    current_customer = None
    rows_to_keep = []
    for _, row in df.iterrows():
        customer_val = row[customer_col]
        doc_val = row[doc_col]
        customer_str = str(customer_val).strip() if pd.notna(customer_val) else ""
        doc_str = str(doc_val).strip() if pd.notna(doc_val) else ""

        # Skip total/subtotal rows
        if customer_str.startswith("Total") or customer_str.startswith("Grand Total"):
            continue
        # Customer header row: has customer name but no document number
        if customer_str and not doc_str:
            current_customer = customer_str
            continue
        # Invoice row: fill in the customer name
        if doc_str and current_customer:
            row = row.copy()
            row[customer_col] = current_customer
        rows_to_keep.append(row)

    return pd.DataFrame(rows_to_keep).reset_index(drop=True)


router = APIRouter(prefix="/invoices", tags=["invoices"])

NETSUITE_COLUMN_MAP = {
    # Invoice number variants
    "Invoice #": "invoice_number",
    "Invoice Number": "invoice_number",
    "Document Number": "invoice_number",
    "Doc Number": "invoice_number",
    "Num": "invoice_number",
    # PO number variants
    "PO #": "po_number",
    "PO Number": "po_number",
    "P.O. No.": "po_number",
    "P.O. Number": "po_number",
    # Date variants
    "Invoice Date": "invoice_date",
    "Date": "invoice_date",
    # Due date
    "Due Date": "due_date",
    # Amount variants
    "Amount": "amount",
    "Total": "amount",
    "Original Amount": "amount",
    # Amount paid
    "Amount Paid": "amount_paid",
    "Payment": "amount_paid",
    # Balance variants
    "Balance": "balance",
    "Balance Due": "balance",
    "Open Balance": "balance",
    "Amount Due": "balance",
    # Currency
    "Currency": "currency",
    # Customer variants
    "Customer": "customer_name",
    "Customer Name": "customer_name",
    "Customer:Project": "customer_name",
    "Name": "customer_name",
    # NetSuite ID
    "NetSuite ID": "netsuite_id",
    "Internal ID": "netsuite_id",
    # Payment terms
    "Terms": "payment_terms_days",
    "Payment Terms": "payment_terms_days",
    # Status
    "Status": "status",
    "Transaction Type": "transaction_type",
    # Notes
    "Notes": "notes",
    "Memo": "notes",
    # Age (days overdue — informational, not stored directly)
    "Age": "age_days",
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
        # Detect NetSuite XML SpreadsheetML format (exported as .xls but actually XML)
        is_xml = content[:100].lstrip().startswith(b'<?xml')
        if is_xml:
            df = _parse_netsuite_xml(content)
        elif file.filename.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
            df = _normalize_grouped_df(df)
        elif file.filename.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(content), engine="xlrd")
        else:
            df = pd.read_csv(io.BytesIO(content))
            header_cols = set(df.columns.str.strip())
            known = {"Document Number", "Invoice #", "Invoice Number", "Customer:Project",
                     "Customer", "Open Balance", "Balance", "Balance Due"}
            if not header_cols & known:
                df = pd.read_csv(io.BytesIO(content), skiprows=1)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {e}")

    # Strip whitespace from column names
    df.columns = df.columns.str.strip()
    df.rename(columns=NETSUITE_COLUMN_MAP, inplace=True)

    found_cols = list(df.columns)
    created = updated = skipped = 0
    errors = []

    for idx, row in df.iterrows():
        try:
            inv_num = str(row.get("invoice_number", "")).strip()
            if not inv_num:
                skipped += 1
                continue

            balance_raw = row.get("balance")
            balance = _parse_amount(balance_raw) if (balance_raw is not None and not pd.isna(balance_raw)) else 0.0
            amount_raw = row.get("amount")
            amount = _parse_amount(amount_raw) if (amount_raw is not None and not pd.isna(amount_raw)) else balance
            amount_paid = _parse_amount(row.get("amount_paid", 0))
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

    # Auto-create/link customers from imported invoices
    _sync_customers_from_invoices(company_id, db)

    # Run aging agent to generate follow-ups and escalations
    from app.agents.aging_agent import run_aging_agent
    run_aging_agent(company_id, db)

    return InvoiceImportResult(created=created, updated=updated, skipped=skipped, errors=errors, columns_found=found_cols)


def _sync_customers_from_invoices(company_id: int, db: Session):
    """Upsert Customer records from invoice customer_name field and link invoices via customer_id."""
    from app.models.customer import Customer

    # Get all invoices without a customer_id that have a customer_name
    invoices = db.query(Invoice).filter(
        Invoice.company_id == company_id,
        Invoice.customer_name.isnot(None),
        Invoice.customer_name != "",
    ).all()

    # Build a name -> Customer map (case-insensitive upsert)
    customer_map: dict[str, Customer] = {}
    for inv in invoices:
        name = (inv.customer_name or "").strip()
        if not name:
            continue
        key = name.lower()
        if key not in customer_map:
            existing = db.query(Customer).filter(
                Customer.company_id == company_id,
                Customer.name == name,
            ).first()
            if not existing:
                existing = Customer(company_id=company_id, name=name)
                db.add(existing)
                db.flush()  # get the id
            customer_map[key] = existing
        inv.customer_id = customer_map[key].id

    db.commit()


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
