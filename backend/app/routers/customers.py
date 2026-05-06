from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd
import io
from app.database import get_db
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User
from app.schemas.customer import CustomerOut, CustomerCreate, CustomerUpdate, CustomerImportResult
from app.routers.deps import current_user, assert_company_access

router = APIRouter(prefix="/customers", tags=["customers"])

CUSTOMER_COLUMN_MAP = {
    "Customer Code": "customer_code",
    "Code": "customer_code",
    "Name": "name",
    "Customer Name": "name",
    "Contact": "contact_name",
    "Contact Name": "contact_name",
    "Email": "email",
    "Phone": "phone",
    "Address": "address",
    "Payment Terms": "payment_terms_days",
    "Terms": "payment_terms_days",
    "Credit Limit": "credit_limit",
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


def _parse_decimal(val) -> Optional[float]:
    if pd.isna(val) or val == "":
        return None
    try:
        return float(str(val).replace(",", "").replace("$", "").strip())
    except Exception:
        return None


@router.get("", response_model=List[CustomerOut])
def list_customers(
    company_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    customers = db.query(Customer).filter(
        Customer.company_id == company_id,
        Customer.is_active == True,
    ).order_by(Customer.name).all()

    result = []
    for c in customers:
        out = CustomerOut.model_validate(c)
        invoices = db.query(Invoice).filter(
            Invoice.customer_id == c.id,
            Invoice.status.in_([InvoiceStatus.open, InvoiceStatus.partial, InvoiceStatus.overdue]),
        ).all()
        out.open_balance = sum(float(i.balance or 0) for i in invoices)
        out.overdue_balance = sum(float(i.balance or 0) for i in invoices if i.status == InvoiceStatus.overdue)
        result.append(out)
    return result


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    assert_company_access(user, c.company_id)
    return c


@router.post("", response_model=CustomerOut)
def create_customer(
    req: CustomerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, req.company_id)
    c = Customer(**req.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    req: CustomerUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    assert_company_access(user, c.company_id)
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.post("/import/{company_id}", response_model=CustomerImportResult)
async def import_customers_csv(
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

    df.rename(columns=CUSTOMER_COLUMN_MAP, inplace=True)
    created = updated = skipped = 0
    errors = []

    for idx, row in df.iterrows():
        try:
            name = str(row.get("name", "")).strip()
            if not name:
                skipped += 1
                continue

            existing = db.query(Customer).filter(
                Customer.company_id == company_id,
                Customer.name == name,
            ).first()

            if existing:
                existing.contact_name = str(row.get("contact_name", "")).strip() or existing.contact_name
                existing.email = str(row.get("email", "")).strip() or existing.email
                existing.phone = str(row.get("phone", "")).strip() or existing.phone
                existing.address = str(row.get("address", "")).strip() or existing.address
                existing.payment_terms_days = _parse_terms(row.get("payment_terms_days"))
                credit = _parse_decimal(row.get("credit_limit"))
                if credit is not None:
                    existing.credit_limit = credit
                existing.customer_code = str(row.get("customer_code", "")).strip() or existing.customer_code
                updated += 1
            else:
                c = Customer(
                    company_id=company_id,
                    customer_code=str(row.get("customer_code", "")).strip() or None,
                    name=name,
                    contact_name=str(row.get("contact_name", "")).strip() or None,
                    email=str(row.get("email", "")).strip() or None,
                    phone=str(row.get("phone", "")).strip() or None,
                    address=str(row.get("address", "")).strip() or None,
                    payment_terms_days=_parse_terms(row.get("payment_terms_days")),
                    credit_limit=_parse_decimal(row.get("credit_limit")),
                )
                db.add(c)
                created += 1
        except Exception as e:
            errors.append(f"Row {idx + 2}: {e}")

    db.commit()
    return CustomerImportResult(created=created, updated=updated, skipped=skipped, errors=errors)
