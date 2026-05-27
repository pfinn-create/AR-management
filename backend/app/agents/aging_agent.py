"""
Aging Agent — monitors overdue invoices per company, fires follow-up sequences,
and raises escalation flags based on company-level thresholds.
"""
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.invoice import Invoice, InvoiceStatus
from app.models.customer import Customer
from app.models.company_settings import CompanySettings
from app.models.todo import TodoItem, TodoCategory, TodoPriority, TodoStatus
from app.models.escalation import EscalationFlag, EscalationStatus
from app.models.followup import FollowUpLog

log = logging.getLogger(__name__)

DEFAULT_INTERVALS = [1, 7, 14, 30, 45]
DEFAULT_ESCALATION_DAYS = 60
DEFAULT_ESCALATION_AMOUNT = Decimal("10000")


def _get_settings(company_id: int, db: Session) -> CompanySettings:
    s = db.query(CompanySettings).filter(CompanySettings.company_id == company_id).first()
    if not s:
        s = CompanySettings(
            company_id=company_id,
            followup_intervals_json=json.dumps(DEFAULT_INTERVALS),
            escalation_days_overdue=DEFAULT_ESCALATION_DAYS,
            escalation_min_amount=DEFAULT_ESCALATION_AMOUNT,
        )
        db.add(s)
        db.flush()
    return s


def _days_overdue(invoice: Invoice) -> int:
    if not invoice.due_date:
        return 0
    due = invoice.due_date if invoice.due_date.tzinfo else invoice.due_date.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - due).days)


def run_aging_agent(company_id: int, db: Session) -> dict:
    """
    Triggered on CSV import and on the daily schedule.
    Returns summary dict.
    """
    settings = _get_settings(company_id, db)
    intervals = json.loads(settings.followup_intervals_json or json.dumps(DEFAULT_INTERVALS))
    esc_days = settings.escalation_days_overdue or DEFAULT_ESCALATION_DAYS
    esc_amount = Decimal(str(settings.escalation_min_amount or DEFAULT_ESCALATION_AMOUNT))

    overdue = db.query(Invoice).filter(
        Invoice.company_id == company_id,
        Invoice.status.in_([InvoiceStatus.open, InvoiceStatus.partial, InvoiceStatus.overdue]),
        Invoice.balance > 0,
    ).all()

    followups_created = 0
    escalations_created = 0

    # Group overdue invoices by customer
    customer_invoices: dict[int, list[Invoice]] = {}
    for inv in overdue:
        if not inv.customer_id:
            continue
        customer_invoices.setdefault(inv.customer_id, []).append(inv)

    for customer_id, invoices in customer_invoices.items():
        total_overdue = sum(float(i.balance or 0) for i in invoices)
        max_days = max(_days_overdue(i) for i in invoices)

        # ── Follow-up sequence ──────────────────────────────────────────────
        for inv in invoices:
            days = _days_overdue(inv)
            if days == 0:
                continue

            # Determine which stage this invoice is at
            current_stage = sum(1 for interval in intervals if days >= interval)
            if current_stage == 0:
                continue

            # Check if we already have a log for this stage
            existing = db.query(FollowUpLog).filter(
                FollowUpLog.company_id == company_id,
                FollowUpLog.invoice_id == inv.id,
                FollowUpLog.sequence_stage == current_stage,
            ).first()

            if existing:
                continue

            # Create follow-up todo
            customer = db.query(Customer).filter(Customer.id == customer_id).first()
            cname = customer.name if customer else f"Customer #{customer_id}"
            todo = TodoItem(
                company_id=company_id,
                category=TodoCategory.overdue_invoice,
                priority=TodoPriority.high if days > 30 else TodoPriority.medium,
                title=f"Follow-up #{current_stage}: {cname} — INV {inv.invoice_number} ({days}d overdue, ${float(inv.balance):,.2f})",
                linked_invoice_id=inv.id,
            )
            db.add(todo)
            db.flush()

            log_entry = FollowUpLog(
                company_id=company_id,
                customer_id=customer_id,
                invoice_id=inv.id,
                sequence_stage=current_stage,
                days_overdue_at_trigger=days,
                todo_id=todo.id,
            )
            db.add(log_entry)
            followups_created += 1

        # ── Escalation check ────────────────────────────────────────────────
        triggers = []
        if max_days >= esc_days:
            triggers.append("days_overdue")
        if Decimal(str(total_overdue)) >= esc_amount:
            triggers.append("high_balance")

        if triggers:
            existing_esc = db.query(EscalationFlag).filter(
                EscalationFlag.company_id == company_id,
                EscalationFlag.customer_id == customer_id,
                EscalationFlag.status.in_([EscalationStatus.flagged, EscalationStatus.under_review]),
            ).first()

            if not existing_esc:
                customer = db.query(Customer).filter(Customer.id == customer_id).first()
                cname = customer.name if customer else f"Customer #{customer_id}"
                reason = " + ".join(triggers)

                todo = TodoItem(
                    company_id=company_id,
                    category=TodoCategory.general,
                    priority=TodoPriority.high,
                    title=f"ESCALATION: {cname} — ${total_overdue:,.2f} overdue ({max_days}d) [{reason}]",
                )
                db.add(todo)
                db.flush()

                flag = EscalationFlag(
                    company_id=company_id,
                    customer_id=customer_id,
                    trigger_reason=reason,
                    days_overdue=max_days,
                    amount_overdue=Decimal(str(total_overdue)),
                    linked_todo_id=todo.id,
                )
                db.add(flag)
                escalations_created += 1

    db.commit()
    log.info(f"[aging_agent] company={company_id} followups={followups_created} escalations={escalations_created}")
    return {
        "agent": "aging",
        "company_id": company_id,
        "overdue_customers": len(customer_invoices),
        "followups_created": followups_created,
        "escalations_created": escalations_created,
    }
