from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
from app.database import get_db
from app.models.email_thread import EmailThread, EmailMessage, ThreadStatus, EmailSource
from app.models.user import User
from app.schemas.email_thread import EmailThreadOut, DraftRequest, DraftOut
from app.routers.deps import current_user, assert_company_access

router = APIRouter(prefix="/emails", tags=["emails"])


@router.get("", response_model=List[EmailThreadOut])
def list_threads(
    company_id: int = Query(...),
    status: Optional[ThreadStatus] = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    assert_company_access(user, company_id)
    q = db.query(EmailThread).filter(EmailThread.company_id == company_id)
    if status:
        q = q.filter(EmailThread.status == status)
    threads = q.order_by(EmailThread.last_message_at.desc()).all()
    return threads


@router.get("/{thread_id}", response_model=EmailThreadOut)
def get_thread(
    thread_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    t = db.query(EmailThread).filter(EmailThread.id == thread_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    assert_company_access(user, t.company_id)
    return t


@router.post("/draft", response_model=DraftOut)
async def create_draft(
    req: DraftRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    thread = db.query(EmailThread).filter(EmailThread.id == req.thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    assert_company_access(user, thread.company_id)

    from app.agents.email_agent import draft_reply
    return await draft_reply(thread, db, instructions=req.instructions)


@router.patch("/{thread_id}/status")
def update_thread_status(
    thread_id: int,
    status: ThreadStatus,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    t = db.query(EmailThread).filter(EmailThread.id == thread_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    assert_company_access(user, t.company_id)
    t.status = status
    db.commit()
    return {"detail": "Updated"}


class DraftEditRequest(BaseModel):
    thread_id: int
    original_body: str
    edited_body: str
    original_subject: str
    edited_subject: str


@router.post("/draft/learn")
async def record_draft_edit(
    req: DraftEditRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Record user edits to an AI draft for future learning."""
    thread = db.query(EmailThread).filter(EmailThread.id == req.thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    assert_company_access(user, thread.company_id)
    from app.agents.email_agent import record_draft_edit as _record
    await _record(
        thread_id=req.thread_id,
        original_body=req.original_body,
        edited_body=req.edited_body,
        original_subject=req.original_subject,
        edited_subject=req.edited_subject,
        editor_user_id=user.id,
        db=db,
    )
    return {"detail": "Learning recorded"}


@router.post("/sync/{company_id}")
async def sync_emails(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Trigger email sync for Gmail and/or Outlook mailboxes linked to this company."""
    assert_company_access(user, company_id)
    from app.services.gmail_service import sync_gmail_threads
    from app.services.outlook_service import sync_outlook_threads

    gmail_result = await sync_gmail_threads(company_id, db)
    outlook_result = await sync_outlook_threads(company_id, db)

    return {
        "gmail": gmail_result,
        "outlook": outlook_result,
    }


@router.post("/{thread_id}/messages")
def add_message(
    thread_id: int,
    sender: str,
    body: str,
    is_outbound: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    t = db.query(EmailThread).filter(EmailThread.id == thread_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    assert_company_access(user, t.company_id)

    msg = EmailMessage(
        thread_id=thread_id,
        sender=sender,
        body_text=body,
        received_at=datetime.now(timezone.utc),
        is_outbound=is_outbound,
    )
    db.add(msg)
    t.last_message_at = datetime.now(timezone.utc)
    if not is_outbound:
        t.status = ThreadStatus.needs_response
        from app.models.todo import TodoItem, TodoCategory, TodoPriority
        db.add(TodoItem(
            company_id=t.company_id,
            category=TodoCategory.unanswered_email,
            priority=TodoPriority.medium,
            title=f"Unanswered email: {t.subject or 'No subject'}",
            linked_thread_id=thread_id,
        ))
    db.commit()
    return {"detail": "Message added"}
