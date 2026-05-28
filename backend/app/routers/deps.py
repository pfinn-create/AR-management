from fastapi import Depends, Header
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.user import User, UserRole


def current_user(db: Session = Depends(get_db)) -> User:
    """No-auth mode: always returns the default admin user."""
    user = db.query(User).filter(User.role == UserRole.ar_manager).first()
    return user


def manager_only(user: User = Depends(current_user)) -> User:
    return user


def assert_company_access(user: User, company_id: int):
    """No-auth mode: all companies are accessible."""
    return
