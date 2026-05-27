from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from decimal import Decimal
from pydantic import BaseModel
from app.database import get_db
from app.models.escalation import EscalationFlag, EscalationStatus
from app.models.user import User
from app.routers.deps import current_user, assert_company_access

router = APIRouter(prefix="/escalations", tags=["escalations"])


class EscalationOut(BaseModel):
    id: int
    company_id: int
    customer_id: int
    trigger_reason: Optional[str]
    days_overdue: Optional[int]
    amount_overdue: Optional[float]
    status: EscalationStatus
    assigned_to: Optional[int]
    resolution_notes: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime
    customer_name: Optional[str] = None

    class Config:
        from_attributes = True


class EscalationUpdate(BaseModel):
    status: Optional[EscalationStatus] = None
    assigned_to: Optional[int] = None
    resolution_notes: Optional[str] = None


def _enrich(flag: EscalationFlag) -> EscalationOut:
    out = EscalationOut.model_validate(flag)
    out.amount_overdue = float(flag.amount_overdue) if flag.amount_overdue else None
    if flag.customer:
        out.customer_name = flag.customer.name
    return out


@router.get("", response_model=List[EscalationOut])
def list_escalations(
    company_id: int = Query(...),
    status: Optional[EscalationStatus] = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    q = db.query(EscalationFlag).filter(EscalationFlag.company_id == company_id)
    if status:
        q = q.filter(EscalationFlag.status == status)
    return [_enrich(f) for f in q.order_by(EscalationFlag.created_at.desc()).all()]


@router.patch("/{flag_id}", response_model=EscalationOut)
def update_escalation(
    flag_id: int,
    req: EscalationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    flag = db.query(EscalationFlag).filter(EscalationFlag.id == flag_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Escalation not found")
    assert_company_access(user, flag.company_id)

    if req.status:
        flag.status = req.status
        if req.status == EscalationStatus.resolved:
            flag.resolved_at = datetime.now(timezone.utc)
    if req.assigned_to is not None:
        flag.assigned_to = req.assigned_to
    if req.resolution_notes:
        flag.resolution_notes = req.resolution_notes

    db.commit()
    db.refresh(flag)
    return _enrich(flag)
