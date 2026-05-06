from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.todo import TodoCategory, TodoPriority, TodoStatus


class TodoOut(BaseModel):
    id: int
    company_id: int
    category: TodoCategory
    priority: TodoPriority
    status: TodoStatus
    title: str
    description: Optional[str]
    assigned_to: Optional[int]
    due_date: Optional[datetime]
    linked_invoice_id: Optional[int]
    linked_thread_id: Optional[int]
    linked_payment_id: Optional[int]
    is_auto_generated: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TodoUpdate(BaseModel):
    status: Optional[TodoStatus] = None
    priority: Optional[TodoPriority] = None
    assigned_to: Optional[int] = None
    due_date: Optional[datetime] = None
    description: Optional[str] = None


class TodoCreate(BaseModel):
    company_id: int
    category: TodoCategory
    priority: TodoPriority = TodoPriority.medium
    title: str
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    due_date: Optional[datetime] = None
    linked_invoice_id: Optional[int] = None
    linked_thread_id: Optional[int] = None
    linked_payment_id: Optional[int] = None
