from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.todo import TodoItem, TodoCategory, TodoStatus, TodoPriority
from app.models.user import User
from app.schemas.todo import TodoOut, TodoUpdate, TodoCreate
from app.routers.deps import current_user, assert_company_access

router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("", response_model=List[TodoOut])
def list_todos(
    company_id: int = Query(...),
    category: Optional[TodoCategory] = None,
    status: Optional[TodoStatus] = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    q = db.query(TodoItem).filter(TodoItem.company_id == company_id)
    if category:
        q = q.filter(TodoItem.category == category)
    if status:
        q = q.filter(TodoItem.status == status)
    else:
        q = q.filter(TodoItem.status != TodoStatus.done)
    return q.order_by(TodoItem.created_at.desc()).all()


@router.post("", response_model=TodoOut)
def create_todo(
    req: TodoCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, req.company_id)
    item = TodoItem(**req.model_dump(), is_auto_generated=False)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{todo_id}", response_model=TodoOut)
def update_todo(
    todo_id: int,
    req: TodoUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    item = db.query(TodoItem).filter(TodoItem.id == todo_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Todo not found")
    assert_company_access(user, item.company_id)
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{todo_id}")
def delete_todo(
    todo_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    item = db.query(TodoItem).filter(TodoItem.id == todo_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Todo not found")
    assert_company_access(user, item.company_id)
    item.status = TodoStatus.done
    db.commit()
    return {"detail": "Marked done"}
