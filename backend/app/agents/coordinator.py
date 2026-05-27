"""
Coordinator Agent — orchestrates all sub-agents on schedule or on-demand.

Schedule:
  - Email reply tracking: every 30 minutes
  - Aging + follow-ups + escalations: daily at 08:00 UTC
  - Collections (disputes/escalation review): daily at 09:00 UTC
  - Gmail sync: every 60 minutes (per company that has tokens)
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.models.company import Company

log = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")


def _all_company_ids(db: Session) -> list[int]:
    return [c.id for c in db.query(Company).filter(Company.is_active == True).all()]


# ── Sub-agent runners ──────────────────────────────────────────────────────

async def run_email_reply_tracking():
    from app.agents.email_agent import check_reply_tracking
    with SessionLocal() as db:
        for company_id in _all_company_ids(db):
            try:
                result = check_reply_tracking(company_id, db)
                if result["threads_resolved"]:
                    log.info(result)
            except Exception as e:
                log.error(f"reply_tracking company={company_id}: {e}")


async def run_aging_all():
    from app.agents.aging_agent import run_aging_agent
    with SessionLocal() as db:
        for company_id in _all_company_ids(db):
            try:
                result = run_aging_agent(company_id, db)
                log.info(result)
            except Exception as e:
                log.error(f"aging_agent company={company_id}: {e}")


async def run_collections_all():
    from app.agents.collections_agent import run_collections_agent
    with SessionLocal() as db:
        for company_id in _all_company_ids(db):
            try:
                result = run_collections_agent(company_id, db)
                log.info(result)
            except Exception as e:
                log.error(f"collections_agent company={company_id}: {e}")


async def run_gmail_sync_all():
    from app.services.gmail_service import sync_gmail_threads
    with SessionLocal() as db:
        for company_id in _all_company_ids(db):
            try:
                await sync_gmail_threads(company_id, db)
            except Exception as e:
                log.error(f"gmail_sync company={company_id}: {e}")


# ── On-demand trigger (called by API endpoints after data uploads) ─────────

async def trigger_for_company(company_id: int, agents: list[str] = None):
    """Run specific agents immediately for a single company."""
    agents = agents or ["aging", "collections", "reply_tracking"]
    with SessionLocal() as db:
        if "aging" in agents:
            from app.agents.aging_agent import run_aging_agent
            try:
                run_aging_agent(company_id, db)
            except Exception as e:
                log.error(f"trigger aging company={company_id}: {e}")

        if "collections" in agents:
            from app.agents.collections_agent import run_collections_agent
            try:
                run_collections_agent(company_id, db)
            except Exception as e:
                log.error(f"trigger collections company={company_id}: {e}")

        if "reply_tracking" in agents:
            from app.agents.email_agent import check_reply_tracking
            try:
                check_reply_tracking(company_id, db)
            except Exception as e:
                log.error(f"trigger reply_tracking company={company_id}: {e}")

        if "gmail_sync" in agents:
            from app.services.gmail_service import sync_gmail_threads
            try:
                await sync_gmail_threads(company_id, db)
            except Exception as e:
                log.error(f"trigger gmail_sync company={company_id}: {e}")


# ── Scheduler setup ────────────────────────────────────────────────────────

def start_scheduler():
    if scheduler.running:
        return

    # Email reply tracking — every 30 minutes
    scheduler.add_job(
        run_email_reply_tracking,
        trigger=IntervalTrigger(minutes=30),
        id="email_reply_tracking",
        replace_existing=True,
    )

    # Gmail sync — every 60 minutes
    scheduler.add_job(
        run_gmail_sync_all,
        trigger=IntervalTrigger(minutes=60),
        id="gmail_sync",
        replace_existing=True,
    )

    # Aging agent — daily at 08:00 UTC
    scheduler.add_job(
        run_aging_all,
        trigger=CronTrigger(hour=8, minute=0),
        id="aging_daily",
        replace_existing=True,
    )

    # Collections agent — daily at 09:00 UTC
    scheduler.add_job(
        run_collections_all,
        trigger=CronTrigger(hour=9, minute=0),
        id="collections_daily",
        replace_existing=True,
    )

    scheduler.start()
    log.info("Coordinator scheduler started")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
