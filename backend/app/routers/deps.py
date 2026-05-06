from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.user import User, UserRole
from app.routers.auth import get_current_user


def get_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization.split(" ", 1)[1]


def current_user(token: str = Depends(get_token), db: Session = Depends(get_db)) -> User:
    return get_current_user(token, db)


def manager_only(user: User = Depends(current_user)) -> User:
    if user.role != UserRole.ar_manager:
        raise HTTPException(status_code=403, detail="AR Manager role required")
    return user


def assert_company_access(user: User, company_id: int):
    if user.role == UserRole.ar_manager:
        return
    accessible = {a.company_id for a in user.company_access}
    if company_id not in accessible:
        raise HTTPException(status_code=403, detail="No access to this company")
