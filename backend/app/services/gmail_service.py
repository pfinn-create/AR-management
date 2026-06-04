"""
Gmail integration via Google API (OAuth 2.0).
Tokens are stored in the oauth_tokens table per company+mailbox.
"""
import base64
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.oauth_token import OAuthToken
from app.models.email_thread import EmailThread, EmailMessage, ThreadStatus, EmailSource
from app.models.customer import Customer
from app.models.todo import TodoItem, TodoCategory, TodoPriority

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def build_flow(state: str = None) -> Flow:
    client_config = {
        "web": {
            "client_id": settings.gmail_client_id,
            "client_secret": settings.gmail_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.gmail_redirect_uri],
        }
    }
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        state=state,
        redirect_uri=settings.gmail_redirect_uri,
    )
    return flow


def get_authorize_url(company_id: int) -> str:
    flow = build_flow()
    state = base64.urlsafe_b64encode(json.dumps({"company_id": company_id}).encode()).decode()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="false",
        prompt="consent",
        state=state,
    )
    return auth_url


def exchange_code(code: str, state_b64: str, db: Session) -> tuple[str, int]:
    """Exchange OAuth code for tokens. Returns (mailbox_email, company_id)."""
    state_data = json.loads(base64.urlsafe_b64decode(state_b64 + "==").decode())
    company_id = state_data["company_id"]

    flow = build_flow(state=state_b64)
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Get the email address from Google
    service = build("oauth2", "v2", credentials=creds)
    user_info = service.userinfo().get().execute()
    mailbox = user_info.get("email", "unknown")

    # Store / update token in DB
    token_expiry = creds.expiry
    if token_expiry and token_expiry.tzinfo is None:
        token_expiry = token_expiry.replace(tzinfo=timezone.utc)

    existing = db.query(OAuthToken).filter(
        OAuthToken.company_id == company_id,
        OAuthToken.provider == "gmail",
        OAuthToken.mailbox == mailbox,
    ).first()

    if existing:
        existing.access_token = creds.token
        existing.refresh_token = creds.refresh_token or existing.refresh_token
        existing.token_expiry = token_expiry
        existing.scopes = " ".join(creds.scopes or SCOPES)
    else:
        db.add(OAuthToken(
            company_id=company_id,
            provider="gmail",
            mailbox=mailbox,
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            token_expiry=token_expiry,
            scopes=" ".join(creds.scopes or SCOPES),
        ))

    db.commit()
    return mailbox, company_id


def _get_credentials(token: OAuthToken, db: Session) -> Optional[Credentials]:
    creds = Credentials(
        token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret,
        scopes=(token.scopes or "").split(),
    )
    if token.token_expiry:
        expiry = token.token_expiry if token.token_expiry.tzinfo else token.token_expiry.replace(tzinfo=timezone.utc)
        creds.expiry = expiry

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token.access_token = creds.token
            expiry = creds.expiry
            if expiry and expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            token.token_expiry = expiry
            db.commit()
        except Exception:
            return None

    return creds


# ---------------------------------------------------------------------------
# Body / header parsing
# ---------------------------------------------------------------------------

def _decode_body(payload: dict) -> str:
    """Recursively extract plain-text body from Gmail message payload."""
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")

    if mime.startswith("multipart/"):
        for part in payload.get("parts", []):
            result = _decode_body(part)
            if result:
                return result

    return ""


def _get_header(headers: list, name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _parse_gmail_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _extract_email_addr(header_val: str) -> str:
    """Extract bare email from 'Name <email@example.com>' format."""
    m = re.search(r"<([^>]+)>", header_val)
    return m.group(1).lower() if m else header_val.lower().strip()


# ---------------------------------------------------------------------------
# Customer matching
# ---------------------------------------------------------------------------

def _match_customer(company_id: int, sender_email: str, db: Session) -> Optional[int]:
    if not sender_email:
        return None
    c = db.query(Customer).filter(
        Customer.company_id == company_id,
        Customer.email.ilike(sender_email),
        Customer.is_active == True,
    ).first()
    return c.id if c else None


# ---------------------------------------------------------------------------
# Main sync
# ---------------------------------------------------------------------------

async def sync_gmail_threads(company_id: int, db: Session) -> dict:
    if not settings.gmail_client_id:
        return {"status": "skipped", "reason": "Gmail not configured — add GMAIL_CLIENT_ID to .env"}

    tokens = db.query(OAuthToken).filter(
        OAuthToken.company_id == company_id,
        OAuthToken.provider == "gmail",
    ).all()

    if not tokens:
        return {"status": "not_connected", "reason": "No Gmail mailboxes connected for this company"}

    total_new = 0
    total_updated = 0
    errors = []

    for token in tokens:
        creds = _get_credentials(token, db)
        if not creds:
            errors.append(f"{token.mailbox}: token refresh failed — reconnect required")
            continue

        try:
            new_t, upd_t = _sync_mailbox(company_id, token.mailbox, creds, db)
            total_new += new_t
            total_updated += upd_t
        except HttpError as e:
            errors.append(f"{token.mailbox}: {e}")
        except Exception as e:
            errors.append(f"{token.mailbox}: {e}")

    return {
        "status": "ok",
        "new_threads": total_new,
        "updated_threads": total_updated,
        "mailboxes_synced": len(tokens),
        "errors": errors,
    }


def _sync_mailbox(company_id: int, mailbox: str, creds: Credentials, db: Session) -> tuple[int, int]:
    service = build("gmail", "v1", credentials=creds)

    # Fetch up to 100 recent threads from INBOX
    response = service.users().threads().list(
        userId="me",
        labelIds=["INBOX"],
        maxResults=100,
    ).execute()

    thread_items = response.get("threads", [])
    new_count = 0
    upd_count = 0

    for item in thread_items:
        gmail_thread_id = item["id"]

        # Fetch full thread with messages
        thread_data = service.users().threads().get(
            userId="me",
            id=gmail_thread_id,
            format="full",
        ).execute()

        messages = thread_data.get("messages", [])
        if not messages:
            continue

        # Build subject + snippet from first message
        first_msg = messages[0]
        headers = first_msg.get("payload", {}).get("headers", [])
        subject = _get_header(headers, "Subject") or "(No subject)"
        snippet = thread_data.get("snippet", "")[:300]

        # Most recent message date
        last_msg = messages[-1]
        last_headers = last_msg.get("payload", {}).get("headers", [])
        last_date = _parse_gmail_date(_get_header(last_headers, "Date"))
        from_addr = _extract_email_addr(_get_header(last_headers, "From"))

        # Upsert thread
        existing = db.query(EmailThread).filter(
            EmailThread.company_id == company_id,
            EmailThread.external_thread_id == gmail_thread_id,
        ).first()

        is_new = existing is None
        if is_new:
            customer_id = _match_customer(company_id, from_addr, db)
            existing = EmailThread(
                company_id=company_id,
                external_thread_id=gmail_thread_id,
                subject=subject,
                snippet=snippet,
                source=EmailSource.gmail,
                mailbox=mailbox,
                status=ThreadStatus.unread,
                last_message_at=last_date or datetime.now(timezone.utc),
                customer_id=customer_id,
            )
            db.add(existing)
            db.flush()
            new_count += 1
        else:
            existing.snippet = snippet
            existing.last_message_at = last_date or existing.last_message_at
            if not existing.customer_id:
                existing.customer_id = _match_customer(company_id, from_addr, db)
            upd_count += 1

        # Sync messages into this thread
        _sync_messages(existing, messages, mailbox, db)

        # Auto-todo for new unread inbound threads
        if is_new:
            db.add(TodoItem(
                company_id=company_id,
                category=TodoCategory.unanswered_email,
                priority=TodoPriority.medium,
                title=f"New email: {subject}",
                linked_thread_id=existing.id,
            ))

    db.commit()
    return new_count, upd_count


def _sync_messages(thread: EmailThread, gmail_messages: list, mailbox: str, db: Session):
    existing_ids = {m.external_message_id for m in thread.messages if m.external_message_id}

    for gm in gmail_messages:
        msg_id = gm["id"]
        if msg_id in existing_ids:
            continue

        payload = gm.get("payload", {})
        headers = payload.get("headers", [])
        sender = _get_header(headers, "From")
        recipient = _get_header(headers, "To")
        date = _parse_gmail_date(_get_header(headers, "Date"))
        body = _decode_body(payload)

        label_ids = gm.get("labelIds", [])
        is_outbound = "SENT" in label_ids
        is_draft = "DRAFT" in label_ids

        db.add(EmailMessage(
            thread_id=thread.id,
            external_message_id=msg_id,
            sender=sender,
            recipient=recipient,
            body_text=body,
            received_at=date or datetime.now(timezone.utc),
            is_outbound=is_outbound,
            is_draft=is_draft,
        ))

    # Update thread status if latest message is inbound (needs response)
    non_draft_messages = [m for m in gmail_messages if "DRAFT" not in m.get("labelIds", [])]
    if non_draft_messages:
        latest = non_draft_messages[-1]
        label_ids = latest.get("labelIds", [])
        if "SENT" not in label_ids and thread.status == ThreadStatus.unread:
            thread.status = ThreadStatus.needs_response


# ---------------------------------------------------------------------------
# Draft creation in Gmail
# ---------------------------------------------------------------------------

def push_draft_to_gmail(
    thread: EmailThread,
    subject: str,
    body: str,
    db: Session,
    attachments: list[tuple[str, bytes]] | None = None,
) -> Optional[str]:
    """
    Create a draft in the Gmail mailbox associated with this thread.
    Returns the Gmail draft ID, or None if push fails.

    attachments: optional list of (filename, file_bytes) tuples.
    """
    token = db.query(OAuthToken).filter(
        OAuthToken.company_id == thread.company_id,
        OAuthToken.provider == "gmail",
        OAuthToken.mailbox == thread.mailbox,
    ).first()

    if not token:
        return None

    creds = _get_credentials(token, db)
    if not creds:
        return None

    try:
        service = build("gmail", "v1", credentials=creds)

        # Build the MIME message
        if attachments:
            mime_msg = MIMEMultipart()
            mime_msg.attach(MIMEText(body, "plain"))
            for filename, file_bytes in attachments:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(file_bytes)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
                mime_msg.attach(part)
        else:
            mime_msg = MIMEText(body, "plain")

        mime_msg["Subject"] = subject
        mime_msg["From"] = thread.mailbox

        # Try to reply-to the thread if we have the original sender
        if thread.messages:
            inbound = [m for m in thread.messages if not m.is_outbound and not m.is_draft]
            if inbound:
                mime_msg["To"] = inbound[-1].sender or ""

        # Encode
        encoded = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
        draft_body = {"message": {"raw": encoded}}

        # Attach to existing thread if we have the Gmail thread ID
        if thread.external_thread_id:
            draft_body["message"]["threadId"] = thread.external_thread_id

        result = service.users().drafts().create(userId="me", body=draft_body).execute()
        return result.get("id")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Mailbox listing
# ---------------------------------------------------------------------------

def list_connected_mailboxes(company_id: int, db: Session) -> list[dict]:
    tokens = db.query(OAuthToken).filter(
        OAuthToken.company_id == company_id,
        OAuthToken.provider == "gmail",
    ).all()
    return [
        {
            "id": t.id,
            "mailbox": t.mailbox,
            "connected_at": t.created_at.isoformat() if t.created_at else None,
            "scopes": t.scopes,
        }
        for t in tokens
    ]


def disconnect_mailbox(token_id: int, company_id: int, db: Session) -> bool:
    token = db.query(OAuthToken).filter(
        OAuthToken.id == token_id,
        OAuthToken.company_id == company_id,
        OAuthToken.provider == "gmail",
    ).first()
    if not token:
        return False
    db.delete(token)
    db.commit()
    return True
