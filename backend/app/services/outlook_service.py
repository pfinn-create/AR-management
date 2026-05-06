"""
Outlook / Microsoft 365 integration via Microsoft Graph API.
Uses MSAL for OAuth. Tokens stored per-company (future: oauth_tokens table).
"""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.email_thread import EmailThread, EmailMessage, ThreadStatus, EmailSource
from app.models.todo import TodoItem, TodoCategory, TodoPriority


async def sync_outlook_threads(company_id: int, db: Session) -> dict:
    """
    Sync Outlook threads for a company via Microsoft Graph.
    Requires OUTLOOK_CLIENT_ID, OUTLOOK_CLIENT_SECRET, OUTLOOK_TENANT_ID in env,
    plus a stored refresh token for the mailbox.
    """
    from app.config import settings
    if not settings.outlook_client_id:
        return {"status": "skipped", "reason": "Outlook not configured"}

    return {"status": "not_configured", "reason": "Outlook OAuth tokens not yet stored for this company"}


def _upsert_thread(
    company_id: int,
    external_thread_id: str,
    subject: str,
    snippet: str,
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
            source=EmailSource.outlook,
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
