"""
Gmail integration via Google API.
OAuth tokens are stored per-company in the database (future: oauth_tokens table).
For now, this module provides the sync skeleton — wire up via /emails/sync endpoint.
"""
import base64
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.email_thread import EmailThread, EmailMessage, ThreadStatus, EmailSource
from app.models.todo import TodoItem, TodoCategory, TodoPriority


async def sync_gmail_threads(company_id: int, db: Session) -> dict:
    """
    Sync Gmail threads for a company.
    Requires GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in env,
    and a stored OAuth refresh token for the mailbox.
    Returns summary of synced threads.
    """
    from app.config import settings
    if not settings.gmail_client_id:
        return {"status": "skipped", "reason": "Gmail not configured"}

    # Placeholder — full OAuth flow and token storage to be set up during onboarding
    return {"status": "not_configured", "reason": "Gmail OAuth tokens not yet stored for this company"}


def _decode_body(payload: dict) -> str:
    body = ""
    if payload.get("body", {}).get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                break
    return body


def _get_header(headers: list, name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _upsert_thread(
    company_id: int,
    external_thread_id: str,
    subject: str,
    snippet: str,
    source: EmailSource,
    mailbox: str,
    db: Session,
) -> EmailThread:
    thread = db.query(EmailThread).filter(
        EmailThread.company_id == company_id,
        EmailThread.external_thread_id == external_thread_id,
    ).first()
    if not thread:
        thread = EmailThread(
            company_id=company_id,
            external_thread_id=external_thread_id,
            subject=subject,
            snippet=snippet,
            source=source,
            mailbox=mailbox,
            status=ThreadStatus.unread,
            last_message_at=datetime.now(timezone.utc),
        )
        db.add(thread)
        db.flush()
        db.add(TodoItem(
            company_id=company_id,
            category=TodoCategory.unanswered_email,
            priority=TodoPriority.medium,
            title=f"New email: {subject or 'No subject'}",
            linked_thread_id=thread.id,
        ))
    return thread
