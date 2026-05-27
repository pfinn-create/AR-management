from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
from app.database import get_db
from app.models.dispute import Dispute, DisputeStatus, DisputeReason
from app.models.user import User
from app.routers.deps import current_user, assert_company_access

router = APIRouter(prefix="/disputes", tags=["disputes"])


class DisputeCreate(BaseModel):
    invoice_id: int
    reason: DisputeReason
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    linked_thread_id: Optional[int] = None


class DisputeUpdate(BaseModel):
    status: Optional[DisputeStatus] = None
    assigned_to: Optional[int] = None
    resolution_notes: Optional[str] = None


class DisputeOut(BaseModel):
    id: int
    company_id: int
    invoice_id: int
    customer_id: Optional[int]
    reason: DisputeReason
    description: Optional[str]
    status: DisputeStatus
    raised_by: int
    assigned_to: Optional[int]
    resolution_notes: Optional[str]
    resolved_at: Optional[datetime]
    linked_thread_id: Optional[int]
    created_at: datetime
    invoice_number: Optional[str] = None
    customer_name: Optional[str] = None

    class Config:
        from_attributes = True


def _enrich(d: Dispute) -> DisputeOut:
    out = DisputeOut.model_validate(d)
    if d.invoice:
        out.invoice_number = d.invoice.invoice_number
        out.customer_name = d.invoice.customer_name
    if d.customer:
        out.customer_name = d.customer.name
    return out


@router.get("", response_model=List[DisputeOut])
def list_disputes(
    company_id: int = Query(...),
    status: Optional[DisputeStatus] = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    q = db.query(Dispute).filter(Dispute.company_id == company_id)
    if status:
        q = q.filter(Dispute.status == status)
    return [_enrich(d) for d in q.order_by(Dispute.created_at.desc()).all()]


@router.get("/{dispute_id}", response_model=DisputeOut)
def get_dispute(
    dispute_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    d = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dispute not found")
    assert_company_access(user, d.company_id)
    return _enrich(d)


@router.post("", response_model=DisputeOut)
def create_dispute(
    company_id: int,
    req: DisputeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    from app.models.invoice import Invoice
    inv = db.query(Invoice).filter(Invoice.id == req.invoice_id, Invoice.company_id == company_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    d = Dispute(
        company_id=company_id,
        invoice_id=req.invoice_id,
        customer_id=inv.customer_id,
        reason=req.reason,
        description=req.description,
        raised_by=user.id,
        assigned_to=req.assigned_to,
        linked_thread_id=req.linked_thread_id,
    )
    db.add(d)

    # Mark invoice as disputed
    from app.models.invoice import InvoiceStatus
    inv.status = InvoiceStatus.disputed

    # Create todo
    from app.models.todo import TodoItem, TodoCategory, TodoPriority
    db.add(TodoItem(
        company_id=company_id,
        category=TodoCategory.missing_invoice_detail,
        priority=TodoPriority.high,
        title=f"Dispute raised: INV {inv.invoice_number} — {req.reason.replace('_', ' ')}",
        linked_invoice_id=req.invoice_id,
        linked_thread_id=req.linked_thread_id,
    ))

    db.commit()
    db.refresh(d)
    return _enrich(d)


@router.patch("/{dispute_id}", response_model=DisputeOut)
def update_dispute(
    dispute_id: int,
    req: DisputeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    d = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dispute not found")
    assert_company_access(user, d.company_id)

    if req.status:
        d.status = req.status
        if req.status in (DisputeStatus.resolved, DisputeStatus.rejected):
            d.resolved_at = datetime.now(timezone.utc)
            # Revert invoice status to open if resolved
            if req.status == DisputeStatus.resolved:
                from app.models.invoice import Invoice, InvoiceStatus
                inv = db.query(Invoice).filter(Invoice.id == d.invoice_id).first()
                if inv:
                    inv.status = InvoiceStatus.open if float(inv.balance or 0) > 0 else InvoiceStatus.paid
    if req.assigned_to is not None:
        d.assigned_to = req.assigned_to
    if req.resolution_notes:
        d.resolution_notes = req.resolution_notes

    db.commit()
    db.refresh(d)
    return _enrich(d)
