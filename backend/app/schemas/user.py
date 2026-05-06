from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.ar_specialist


class UserCreate(UserBase):
    password: str
    company_ids: List[int] = []


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    company_ids: Optional[List[int]] = None


class UserOut(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    company_ids: List[int] = []

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
