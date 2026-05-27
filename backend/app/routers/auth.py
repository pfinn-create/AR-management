from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.database import get_db
from app.models.user import User, UserCompanyAccess, UserRole
from app.models.company import Company
from app.schemas.user import UserCreate, UserOut, Token, LoginRequest, UserUpdate
from app.config import settings
from typing import List, Optional

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def get_current_user(token: str, db: Session) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _user_out(user: User) -> UserOut:
    company_ids = [a.company_id for a in user.company_access]
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        email_consent=user.email_consent or False,
        email_consent_at=user.email_consent_at,
        created_at=user.created_at,
        company_ids=company_ids,
    )


@router.post("/login", response_model=Token)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    token = create_access_token({"sub": user.id})
    return Token(access_token=token, token_type="bearer", user=_user_out(user))


@router.get("/me", response_model=UserOut)
def get_me(
    db: Session = Depends(get_db),
    token: str = Depends(lambda: None),
):
    # Token handled in main via header extraction
    raise HTTPException(status_code=501, detail="Use /auth/me with Authorization header")


@router.post("/users", response_model=UserOut)
def create_user(req: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=req.email,
        full_name=req.full_name,
        hashed_password=hash_password(req.password),
        role=req.role,
    )
    db.add(user)
    db.flush()
    for cid in req.company_ids:
        db.add(UserCompanyAccess(user_id=user.id, company_id=cid))
    db.commit()
    db.refresh(user)
    return _user_out(user)
