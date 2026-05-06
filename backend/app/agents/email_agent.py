import json
import re
from sqlalchemy.orm import Session
from anthropic import AsyncAnthropic
from app.config import settings
from app.models.email_thread import EmailThread, EmailMessage, ThreadStatus
from app.models.invoice import Invoice
from app.models.customer import Customer
from app.models.todo import TodoItem, TodoCategory, TodoPriority, TodoStatus
from app.schemas.email_thread import DraftOut

client = AsyncAnthropic(api_key=settings.anthropic_api_key)


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

{"Additional instructions: " + instructions if instructions else ""}

Draft a professional, concise reply that:
1. Addresses the customer's specific query
2. References relevant invoice numbers if applicable
3. Is courteous but firm on payment matters
4. Uses a professional tone appropriate for accounts receivable

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

    # Push to Gmail Drafts folder if this thread came from Gmail
    gmail_draft_id = None
    if thread.source and thread.source.value == "gmail":
        try:
            from app.services.gmail_service import push_draft_to_gmail
            gmail_draft_id = push_draft_to_gmail(thread, subject, body, db)
        except Exception:
            pass  # Draft still saved locally even if Gmail push fails

    # Save draft locally
    draft_msg = EmailMessage(
        thread_id=thread.id,
        sender=thread.mailbox or "ar@company.com",
        body_text=body,
        is_draft=True,
        is_outbound=True,
        draft_external_id=gmail_draft_id,
    )
    db.add(draft_msg)

    # Update thread status and create todo
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
