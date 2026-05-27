"""
Collections Agent — processes disputes, reviews open escalations,
and creates/updates related todos.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.dispute import Dispute, DisputeStatus
from app.models.escalation import EscalationFlag, EscalationStatus
from app.models.todo import TodoItem, TodoCategory, TodoPriority, TodoStatus
from app.models.invoice import Invoice, InvoiceStatus

log = logging.getLogger(__name__)


def run_collections_agent(company_id: int, db: Session) -> dict:
    """
    Daily agent run:
    1. Check new disputes → mark invoices as disputed, create todos.
    2. Review open escalations → update todos if resolved invoices exist.
    """
    disputes_processed = 0
    escalations_reviewed = 0

    # ── Mark disputed invoices ──────────────────────────────────────────────
    new_disputes = db.query(Dispute).filter(
        Dispute.company_id == company_id,
        Dispute.status == DisputeStatus.open,
    ).all()

    for dispute in new_disputes:
        inv = db.query(Invoice).filter(Invoice.id == dispute.invoice_id).first()
        if inv and inv.status != InvoiceStatus.disputed:
            inv.status = InvoiceStatus.disputed
            disputes_processed += 1

    # ── Auto-close escalations for fully paid customers ──────────────────
    open_flags = db.query(EscalationFlag).filter(
        EscalationFlag.company_id == company_id,
        EscalationFlag.status.in_([EscalationStatus.flagged, EscalationStatus.under_review]),
    ).all()

    for flag in open_flags:
        # Check if customer still has outstanding balance
        outstanding = db.query(Invoice).filter(
            Invoice.company_id == company_id,
            Invoice.customer_id == flag.customer_id,
            Invoice.status.in_([InvoiceStatus.open, InvoiceStatus.partial, InvoiceStatus.overdue]),
            Invoice.balance > 0,
        ).first()

        if not outstanding:
            flag.status = EscalationStatus.resolved
            flag.resolved_at = datetime.now(timezone.utc)
            flag.resolution_notes = "Auto-resolved: no outstanding balance"
            # Archive linked todo
            if flag.linked_todo_id:
                todo = db.query(TodoItem).filter(TodoItem.id == flag.linked_todo_id).first()
                if todo:
                    todo.status = TodoStatus.archived
            escalations_reviewed += 1

    db.commit()
    log.info(f"[collections_agent] company={company_id} disputes={disputes_processed} escalations_reviewed={escalations_reviewed}")
    return {
        "agent": "collections",
        "company_id": company_id,
        "disputes_processed": disputes_processed,
        "escalations_auto_resolved": escalations_reviewed,
    }
