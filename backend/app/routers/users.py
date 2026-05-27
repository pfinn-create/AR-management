from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from app.database import get_db
from app.models.user import User, UserCompanyAccess
from app.schemas.user import UserOut, UserUpdate, UserCreate, EmailConsentRequest
from app.routers.deps import current_user, manager_only
from app.routers.auth import hash_password, _user_out

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    user: User = Depends(manager_only),
):
    users = db.query(User).filter(User.is_active == True).all()
    return [_user_out(u) for u in users]


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(current_user)):
    return _user_out(user)


@router.post("/me/email-consent", response_model=UserOut)
def set_email_consent(
    req: EmailConsentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Record the user's email access consent decision (asked once on first login)."""
    user.email_consent = req.consent
    user.email_consent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.post("", response_model=UserOut)
def create_user(
    req: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(manager_only),
):
    from app.routers.auth import create_user as _create
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    u = User(
        email=req.email,
        full_name=req.full_name,
        hashed_password=hash_password(req.password),
        role=req.role,
    )
    db.add(u)
    db.flush()
    for cid in req.company_ids:
        db.add(UserCompanyAccess(user_id=u.id, company_id=cid))
    db.commit()
    db.refresh(u)
    return _user_out(u)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    req: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(manager_only),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    for k, v in req.model_dump(exclude={"company_ids"}, exclude_none=True).items():
        setattr(u, k, v)
    if req.company_ids is not None:
        db.query(UserCompanyAccess).filter(UserCompanyAccess.user_id == user_id).delete()
        for cid in req.company_ids:
            db.add(UserCompanyAccess(user_id=user_id, company_id=cid))
    db.commit()
    db.refresh(u)
    return _user_out(u)


@router.delete("/{user_id}")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(manager_only),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    u.is_active = False
    db.commit()
    return {"detail": "User deactivated"}
