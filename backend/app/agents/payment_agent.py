import re
import json
from sqlalchemy.orm import Session
from anthropic import AsyncAnthropic
from app.config import settings
from app.models.payment import Payment, RemittanceLine, MatchConfidence, PaymentStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.todo import TodoItem, TodoCategory, TodoPriority
from app.schemas.payment import PaymentMatchResult

client = AsyncAnthropic(api_key=settings.anthropic_api_key)


def _extract_invoice_numbers(text: str) -> list[str]:
    patterns = [
        r'\bINV[-\s]?\d+\b',
        r'\b\d{4,10}\b',
        r'invoice\s*#?\s*(\w+)',
        r'inv\s*#?\s*(\w+)',
    ]
    found = []
    for pattern in patterns:
        matches = re.findall(pattern, text or "", re.IGNORECASE)
        found.extend(matches)
    return list(set(found))


async def match_payment(payment: Payment, db: Session) -> PaymentMatchResult:
    open_invoices = db.query(Invoice).filter(
        Invoice.company_id == payment.company_id,
        Invoice.status.in_([InvoiceStatus.open, InvoiceStatus.partial, InvoiceStatus.overdue]),
        Invoice.balance > 0,
    ).all()

    invoice_list = [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "customer_name": inv.customer_name,
            "balance": float(inv.balance or 0),
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
        }
        for inv in open_invoices
    ]

    payment_context = {
        "payment_id": payment.id,
        "amount": float(payment.amount),
        "payer_name": payment.payer_name,
        "reference_number": payment.reference_number,
        "memo": payment.memo,
        "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
    }

    prompt = f"""You are an accounts receivable payment matching agent.

Payment received:
{json.dumps(payment_context, indent=2)}

Open invoices to match against:
{json.dumps(invoice_list, indent=2)}

Your task:
1. Analyze the payment details (payer name, reference number, memo, amount) against open invoices.
2. Identify the most likely invoice(s) this payment should be applied to.
3. A single payment can match multiple invoices (partial amounts).
4. Assign a confidence level: "high" (clear match), "medium" (likely match), "low" (possible), "flagged" (unclear, needs human review).

Respond ONLY with valid JSON:
{{
  "matches": [
    {{
      "invoice_id": <int>,
      "invoice_number": "<str>",
      "amount_to_apply": <float>,
      "confidence": "high|medium|low|flagged",
      "reason": "<brief reason>"
    }}
  ],
  "unmatched_amount": <float>,
  "notes": "<overall summary for the AR team>"
}}

If no clear match, return empty matches array with unmatched_amount equal to total payment amount."""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)
    except Exception as e:
        data = {"matches": [], "unmatched_amount": float(payment.amount), "notes": f"AI matching failed: {e}"}

    # Persist remittance lines
    db.query(RemittanceLine).filter(RemittanceLine.payment_id == payment.id).delete()

    matched = 0
    flagged = 0

    for match in data.get("matches", []):
        inv_id = match.get("invoice_id")
        confidence_str = match.get("confidence", "flagged")
        try:
            confidence = MatchConfidence(confidence_str)
        except ValueError:
            confidence = MatchConfidence.flagged

        line = RemittanceLine(
            payment_id=payment.id,
            invoice_id=inv_id,
            invoice_number_raw=match.get("invoice_number"),
            amount=match.get("amount_to_apply"),
            match_confidence=confidence,
            notes=match.get("reason"),
        )
        db.add(line)
        if confidence in (MatchConfidence.high, MatchConfidence.medium):
            matched += 1
        else:
            flagged += 1

    unmatched = float(data.get("unmatched_amount", 0))
    if unmatched > 0.01:
        line = RemittanceLine(
            payment_id=payment.id,
            invoice_id=None,
            invoice_number_raw=None,
            amount=unmatched,
            match_confidence=MatchConfidence.flagged,
            notes=f"Unmatched amount — needs manual review",
        )
        db.add(line)
        flagged += 1

    payment.status = PaymentStatus.matched if matched > 0 else PaymentStatus.unmatched
    payment.ai_notes = data.get("notes", "")

    # Create todo if flagged
    if flagged > 0:
        existing_todo = db.query(TodoItem).filter(
            TodoItem.linked_payment_id == payment.id,
            TodoItem.category == TodoCategory.payment_review,
        ).first()
        if not existing_todo:
            db.add(TodoItem(
                company_id=payment.company_id,
                category=TodoCategory.payment_review,
                priority=TodoPriority.high,
                title=f"Payment ${float(payment.amount):,.2f} from {payment.payer_name or 'Unknown'} — {flagged} line(s) need review",
                linked_payment_id=payment.id,
            ))

    db.commit()
    return PaymentMatchResult(
        payment_id=payment.id,
        lines_matched=matched,
        lines_flagged=flagged,
        ai_notes=data.get("notes", ""),
    )
