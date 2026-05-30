from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.utils.logger import get_logger

logger = get_logger(__name__)
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


def start_scheduler() -> None:
    """Starts the APScheduler background job that checks for due follow-ups."""
    from app.services.followup_service import process_due_follow_ups
    scheduler = get_scheduler()
    scheduler.add_job(
        process_due_follow_ups,
        trigger=IntervalTrigger(minutes=5),
        id="process_follow_ups",
        name="Process Due Follow-Ups",
        replace_existing=True,
        misfire_grace_time=120,
    )
    scheduler.start()
    logger.info("scheduler_started", job_count=len(scheduler.get_jobs()))


def stop_scheduler() -> None:
    """Stops the scheduler cleanly on app shutdown."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
