import json
import re
import difflib
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from anthropic import AsyncAnthropic
from app.config import settings
from app.models.email_thread import EmailThread, EmailMessage, ThreadStatus
from app.models.invoice import Invoice
from app.models.customer import Customer
from app.models.todo import TodoItem, TodoCategory, TodoPriority, TodoStatus
from app.models.draft_learning import DraftLearning
from app.models.followup import FollowUpLog
from app.schemas.email_thread import DraftOut

client = AsyncAnthropic(api_key=settings.anthropic_api_key)


# ── Draft generation ───────────────────────────────────────────────────────

async def draft_reply(
    thread: EmailThread,
    db: Session,
    instructions: str = None,
) -> DraftOut:
    messages = thread.messages
    customer = thread.customer

    invoice_context = []
    if customer:
        invoices = db.query(Invoice).filter(
            Invoice.customer_id == customer.id,
            Invoice.company_id == thread.company_id,
        ).order_by(Invoice.due_date.desc()).limit(10).all()
        invoice_context = [
            {
                "invoice_number": inv.invoice_number,
                "amount": float(inv.amount),
                "balance": float(inv.balance or 0),
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "status": inv.status.value,
            }
            for inv in invoices
        ]

    # Load learning history for this customer
    learning_context = _get_learning_context(thread.customer_id, thread.company_id, db)

    conversation = "\n\n".join([
        f"{'[OUTBOUND]' if m.is_outbound else '[INBOUND]'} From: {m.sender}\n{m.body_text or ''}"
        for m in messages if not m.is_draft
    ])

    customer_info = {}
    if customer:
        customer_info = {
            "name": customer.name,
            "contact": customer.contact_name,
            "payment_terms": f"Net {customer.payment_terms_days}",
        }

    prompt = f"""You are a professional accounts receivable specialist drafting an email reply.

Thread subject: {thread.subject or 'No subject'}
Customer: {json.dumps(customer_info) if customer_info else 'Unknown'}
Open invoices for this customer: {json.dumps(invoice_context) if invoice_context else 'None found'}

Email conversation so far:
---
{conversation}
---

{f"Past draft corrections for this customer (learn from these):{chr(10)}{learning_context}" if learning_context else ""}

{"Additional instructions: " + instructions if instructions else ""}

Draft a professional, concise reply that:
1. Addresses the customer's specific query
2. References relevant invoice numbers if applicable
3. Is courteous but firm on payment matters
4. Applies any lessons from past corrections for this customer

Respond ONLY with valid JSON:
{{
  "subject": "<reply subject line>",
  "body": "<full email body text, plain text, no HTML>"
}}"""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)
    except Exception as e:
        data = {
            "subject": f"Re: {thread.subject or 'Your inquiry'}",
            "body": f"Thank you for your email. We will review your query and respond shortly.\n\n[AI drafting failed: {e}]",
        }

    subject = data.get("subject", f"Re: {thread.subject or 'Your inquiry'}")
    body = data.get("body", "")

    # Push to Gmail Drafts if connected
    gmail_draft_id = None
    if thread.source and thread.source.value == "gmail":
        try:
            from app.services.gmail_service import push_draft_to_gmail
            gmail_draft_id = push_draft_to_gmail(thread, subject, body, db)
        except Exception:
            pass

    draft_msg = EmailMessage(
        thread_id=thread.id,
        sender=thread.mailbox or "ar@company.com",
        body_text=body,
        is_draft=True,
        is_outbound=True,
        draft_external_id=gmail_draft_id,
    )
    db.add(draft_msg)

    thread.status = ThreadStatus.draft_ready
    existing_todo = db.query(TodoItem).filter(
        TodoItem.linked_thread_id == thread.id,
        TodoItem.category == TodoCategory.draft_approval,
        TodoItem.status != TodoStatus.done,
    ).first()
    if not existing_todo:
        db.add(TodoItem(
            company_id=thread.company_id,
            category=TodoCategory.draft_approval,
            priority=TodoPriority.medium,
            title=f"Review draft reply: {thread.subject or 'Email thread'}",
            linked_thread_id=thread.id,
        ))

    db.commit()
    db.refresh(draft_msg)

    return DraftOut(
        thread_id=thread.id,
        draft_body=body,
        subject=subject,
        external_draft_id=gmail_draft_id,
    )


# ── Draft learning ─────────────────────────────────────────────────────────

async def record_draft_edit(
    thread_id: int,
    original_body: str,
    edited_body: str,
    original_subject: str,
    edited_subject: str,
    editor_user_id: int,
    db: Session,
) -> DraftLearning:
    """
    Called when a user submits an edited version of an AI draft.
    Summarises the diff using Claude and stores for future learning.
    """
    thread = db.query(EmailThread).filter(EmailThread.id == thread_id).first()
    if not thread:
        return None

    diff_lines = list(difflib.unified_diff(
        original_body.splitlines(),
        edited_body.splitlines(),
        lineterm="",
        n=2,
    ))
    diff_text = "\n".join(diff_lines[:80])   # cap at 80 lines

    diff_summary = ""
    if diff_text:
        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{
                    "role": "user",
                    "content": f"Summarise in 1-3 bullet points what an AR professional changed in this email draft and why it matters for future drafts:\n\n{diff_text}",
                }],
            )
            diff_summary = response.content[0].text.strip()
        except Exception:
            diff_summary = f"Body changed ({len(diff_lines)} diff lines)"

    learning = DraftLearning(
        company_id=thread.company_id,
        customer_id=thread.customer_id,
        thread_id=thread_id,
        original_subject=original_subject,
        original_body=original_body,
        edited_subject=edited_subject,
        edited_body=edited_body,
        diff_summary=diff_summary,
        edited_by=editor_user_id,
    )
    db.add(learning)
    db.commit()
    return learning


def _get_learning_context(customer_id: int | None, company_id: int, db: Session) -> str:
    """Fetch recent learning summaries for a customer to include in prompt context."""
    if not customer_id:
        return ""
    records = db.query(DraftLearning).filter(
        DraftLearning.customer_id == customer_id,
        DraftLearning.company_id == company_id,
        DraftLearning.diff_summary.isnot(None),
    ).order_by(DraftLearning.created_at.desc()).limit(5).all()
    if not records:
        return ""
    return "\n".join(f"- {r.diff_summary}" for r in records if r.diff_summary)


# ── Reply tracking ─────────────────────────────────────────────────────────

def check_reply_tracking(company_id: int, db: Session) -> dict:
    """
    For each thread in draft_ready status: if the most recent non-draft message
    is inbound (customer replied), close the draft_approval todo and mark responded.
    """
    resolved = 0
    threads = db.query(EmailThread).filter(
        EmailThread.company_id == company_id,
        EmailThread.status == ThreadStatus.draft_ready,
    ).all()

    for thread in threads:
        non_draft = [m for m in thread.messages if not m.is_draft]
        if not non_draft:
            continue
        latest = max(non_draft, key=lambda m: m.received_at or datetime.min.replace(tzinfo=timezone.utc))
        if latest.is_outbound:
            continue  # no customer reply yet

        # Customer replied → close open draft approval todos for this thread
        open_todos = db.query(TodoItem).filter(
            TodoItem.linked_thread_id == thread.id,
            TodoItem.category == TodoCategory.draft_approval,
            TodoItem.status.notin_([TodoStatus.done, TodoStatus.archived]),
        ).all()
        for t in open_todos:
            t.status = TodoStatus.archived

        # Also close unanswered email todos
        open_email_todos = db.query(TodoItem).filter(
            TodoItem.linked_thread_id == thread.id,
            TodoItem.category == TodoCategory.unanswered_email,
            TodoItem.status.notin_([TodoStatus.done, TodoStatus.archived]),
        ).all()
        for t in open_email_todos:
            t.status = TodoStatus.archived

        thread.status = ThreadStatus.responded

        # Mark any follow-up logs as replied
        db.query(FollowUpLog).filter(
            FollowUpLog.thread_id == thread.id,
        ).update({"was_replied_to": True})

        resolved += 1

    db.commit()
    return {"agent": "email_reply_tracker", "company_id": company_id, "threads_resolved": resolved}
