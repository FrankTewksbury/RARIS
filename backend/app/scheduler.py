"""Background job scheduler for periodic tasks."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import async_session

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _scheduled_change_monitor():
    """Run the change monitor on schedule."""
    from app.feedback.monitor import run_change_monitor

    try:
        async with async_session() as db:
            result = await run_change_monitor(db)
            logger.info(
                "Scheduled monitor: %d checked, %d changes",
                result["sources_checked"],
                result["changes_detected"],
            )
    except Exception:
        logger.exception("Scheduled change monitor failed")


async def _scheduled_accuracy_snapshot():
    """Take a periodic accuracy snapshot for trend tracking."""
    from datetime import UTC, datetime

    from sqlalchemy import func, select

    from app.models.feedback import (
        AccuracySnapshot,
        FeedbackType,
        ResponseFeedback,
    )
    from app.models.manifest import Source

    try:
        async with async_session() as db:
            # Count feedback by type
            type_counts: dict[str, int] = {}
            for ftype in FeedbackType:
                count = (
                    await db.execute(
                        select(func.count()).select_from(ResponseFeedback).where(
                            ResponseFeedback.feedback_type == ftype
                        )
                    )
                ).scalar() or 0
                type_counts[ftype.value] = count

            total = sum(type_counts.values())
            correct = type_counts.get("correct", 0)
            inaccurate = type_counts.get("inaccurate", 0)

            accuracy_denominator = correct + inaccurate
            accuracy_score = correct / accuracy_denominator if accuracy_denominator > 0 else 1.0

            resolved = (
                await db.execute(
                    select(func.count()).select_from(ResponseFeedback).where(
                        ResponseFeedback.status.in_(["resolved", "dismissed"])
                    )
                )
            ).scalar() or 0
            resolution_rate = resolved / total if total > 0 else 1.0

            avg_conf = (
                await db.execute(select(func.avg(Source.confidence)))
            ).scalar() or 0.0

            snapshot = AccuracySnapshot(
                snapshot_date=datetime.now(UTC),
                total_feedback=total,
                correct_count=correct,
                inaccurate_count=inaccurate,
                outdated_count=type_counts.get("outdated", 0),
                incomplete_count=type_counts.get("incomplete", 0),
                irrelevant_count=type_counts.get("irrelevant", 0),
                accuracy_score=round(accuracy_score, 3),
                resolution_rate=round(resolution_rate, 3),
                avg_confidence=round(float(avg_conf), 3),
            )
            db.add(snapshot)
            await db.commit()
            logger.info("Accuracy snapshot taken: score=%.3f", accuracy_score)

    except Exception:
        logger.exception("Scheduled accuracy snapshot failed")


def configure_scheduler() -> None:
    """Configure scheduled jobs based on settings."""
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled")
        return

    # Change monitor — runs at configured hour (default: 2 AM)
    scheduler.add_job(
        _scheduled_change_monitor,
        trigger=CronTrigger(hour=settings.monitor_schedule_hour, minute=0),
        id="change_monitor",
        name="Regulatory Change Monitor",
        replace_existing=True,
    )

    # Accuracy snapshot — runs at configured hour (default: 3 AM)
    scheduler.add_job(
        _scheduled_accuracy_snapshot,
        trigger=CronTrigger(hour=settings.snapshot_schedule_hour, minute=0),
        id="accuracy_snapshot",
        name="Accuracy Snapshot",
        replace_existing=True,
    )

    logger.info(
        "Scheduler configured: monitor@%02d:00, snapshot@%02d:00",
        settings.monitor_schedule_hour,
        settings.snapshot_schedule_hour,
    )
