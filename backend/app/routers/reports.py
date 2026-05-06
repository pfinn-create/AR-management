from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.user import User
from app.routers.deps import current_user, assert_company_access

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/aging/{company_id}")
def aging_report(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    now = datetime.now(timezone.utc)

    invoices = db.query(Invoice).filter(
        Invoice.company_id == company_id,
        Invoice.status.in_([InvoiceStatus.open, InvoiceStatus.partial, InvoiceStatus.overdue]),
        Invoice.balance > 0,
    ).all()

    buckets = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "over_90": 0.0}

    for inv in invoices:
        balance = float(inv.balance or 0)
        if not inv.due_date:
            buckets["current"] += balance
            continue
        due = inv.due_date if inv.due_date.tzinfo else inv.due_date.replace(tzinfo=timezone.utc)
        days_past = (now - due).days
        if days_past <= 0:
            buckets["current"] += balance
        elif days_past <= 30:
            buckets["1_30"] += balance
        elif days_past <= 60:
            buckets["31_60"] += balance
        elif days_past <= 90:
            buckets["61_90"] += balance
        else:
            buckets["over_90"] += balance

    return {
        "company_id": company_id,
        "as_of": now.isoformat(),
        "aging": buckets,
        "total": sum(buckets.values()),
    }


@router.get("/aging-by-customer/{company_id}")
def aging_by_customer(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    now = datetime.now(timezone.utc)

    invoices = db.query(Invoice).filter(
        Invoice.company_id == company_id,
        Invoice.status.in_([InvoiceStatus.open, InvoiceStatus.partial, InvoiceStatus.overdue]),
        Invoice.balance > 0,
    ).all()

    customers: dict = {}
    for inv in invoices:
        cname = inv.customer_name or f"Customer #{inv.customer_id or 'Unknown'}"
        if cname not in customers:
            customers[cname] = {"name": cname, "current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "over_90": 0.0, "total": 0.0}
        balance = float(inv.balance or 0)
        customers[cname]["total"] += balance
        if not inv.due_date:
            customers[cname]["current"] += balance
            continue
        due = inv.due_date if inv.due_date.tzinfo else inv.due_date.replace(tzinfo=timezone.utc)
        days_past = (now - due).days
        if days_past <= 0:
            customers[cname]["current"] += balance
        elif days_past <= 30:
            customers[cname]["1_30"] += balance
        elif days_past <= 60:
            customers[cname]["31_60"] += balance
        elif days_past <= 90:
            customers[cname]["61_90"] += balance
        else:
            customers[cname]["over_90"] += balance

    return sorted(customers.values(), key=lambda x: x["total"], reverse=True)


@router.get("/trends/{company_id}")
def monthly_trends(
    company_id: int,
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    now = datetime.now(timezone.utc)
    result = []

    for i in range(months - 1, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=i * 30)).replace(day=1, hour=0, minute=0, second=0)
        month_end = (month_start + timedelta(days=32)).replace(day=1)
        label = month_start.strftime("%b %Y")

        invoiced = db.query(func.sum(Invoice.amount)).filter(
            Invoice.company_id == company_id,
            Invoice.invoice_date >= month_start,
            Invoice.invoice_date < month_end,
        ).scalar() or 0.0

        collected = db.query(func.sum(Payment.amount)).filter(
            Payment.company_id == company_id,
            Payment.payment_date >= month_start,
            Payment.payment_date < month_end,
            Payment.status == "applied",
        ).scalar() or 0.0

        overdue = db.query(func.sum(Invoice.balance)).filter(
            Invoice.company_id == company_id,
            Invoice.status == InvoiceStatus.overdue,
            Invoice.due_date < month_end,
        ).scalar() or 0.0

        result.append({
            "month": label,
            "invoiced": float(invoiced),
            "collected": float(collected),
            "overdue": float(overdue),
        })

    return result


@router.get("/summary/{company_id}")
def ar_summary(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    now = datetime.now(timezone.utc)

    total_open = db.query(func.sum(Invoice.balance)).filter(
        Invoice.company_id == company_id,
        Invoice.status.in_([InvoiceStatus.open, InvoiceStatus.partial, InvoiceStatus.overdue]),
    ).scalar() or 0.0

    total_overdue = db.query(func.sum(Invoice.balance)).filter(
        Invoice.company_id == company_id,
        Invoice.status == InvoiceStatus.overdue,
    ).scalar() or 0.0

    invoice_count = db.query(func.count(Invoice.id)).filter(
        Invoice.company_id == company_id,
        Invoice.status.in_([InvoiceStatus.open, InvoiceStatus.partial, InvoiceStatus.overdue]),
    ).scalar() or 0

    pending_payments = db.query(func.count(Payment.id)).filter(
        Payment.company_id == company_id,
        Payment.status == "pending_review",
    ).scalar() or 0

    return {
        "company_id": company_id,
        "total_ar_balance": float(total_open),
        "total_overdue": float(total_overdue),
        "open_invoice_count": invoice_count,
        "pending_payment_reviews": pending_payments,
    }
