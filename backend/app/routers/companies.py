from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.database import get_db
from app.models.company import Company
from app.models.invoice import Invoice, InvoiceStatus
from app.models.todo import TodoItem, TodoStatus
from app.models.email_thread import EmailThread, ThreadStatus
from app.models.user import User, UserCompanyAccess
from app.schemas.company import CompanyOut, CompanySummary, CompanyCreate, CompanyUpdate
from app.routers.deps import current_user, manager_only

router = APIRouter(prefix="/companies", tags=["companies"])


def _accessible_company_ids(user: User) -> List[int] | None:
    from app.models.user import UserRole
    if user.role == UserRole.ar_manager:
        return None  # all
    return [a.company_id for a in user.company_access]


@router.get("", response_model=List[CompanySummary])
def list_companies(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    q = db.query(Company).filter(Company.is_active == True)
    ids = _accessible_company_ids(user)
    if ids is not None:
        q = q.filter(Company.id.in_(ids))
    companies = q.all()

    result = []
    for c in companies:
        open_inv = db.query(Invoice).filter(
            Invoice.company_id == c.id,
            Invoice.status.in_([InvoiceStatus.open, InvoiceStatus.partial, InvoiceStatus.overdue])
        ).all()
        total_balance = sum(float(i.balance or 0) for i in open_inv)
        overdue = sum(float(i.balance or 0) for i in open_inv if i.status == InvoiceStatus.overdue)
        todos = db.query(TodoItem).filter(
            TodoItem.company_id == c.id, TodoItem.status != TodoStatus.done
        ).count()
        unanswered = db.query(EmailThread).filter(
            EmailThread.company_id == c.id,
            EmailThread.status.in_([ThreadStatus.unread, ThreadStatus.needs_response])
        ).count()
        result.append(CompanySummary(
            id=c.id, code=c.code, name=c.name,
            default_payment_terms_days=c.default_payment_terms_days,
            is_active=c.is_active, created_at=c.created_at,
            open_invoices_count=len(open_inv),
            total_ar_balance=total_balance,
            overdue_amount=overdue,
            open_todos_count=todos,
            unanswered_emails_count=unanswered,
        ))
    return result


@router.get("/{company_id}", response_model=CompanySummary)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    from app.routers.deps import assert_company_access
    assert_company_access(user, company_id)
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    return c


@router.post("", response_model=CompanyOut)
def create_company(
    req: CompanyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(manager_only),
):
    c = Company(**req.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: int,
    req: CompanyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(manager_only),
):
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c
