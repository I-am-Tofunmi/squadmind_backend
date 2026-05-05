"""
SquadMind – Celery Application
Background task queue for transaction syncing, fraud scanning, and scheduled reports.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "squadmind",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.tasks.sync_transactions",
        "app.workers.tasks.fraud_scan",
        "app.workers.tasks.forecast_tasks",
        "app.workers.tasks.alert_tasks",
    ],
)

# ── Celery Configuration ──────────────────────────────────────────────────────
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Lagos",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,               # only ack after task completes (safer)
    worker_prefetch_multiplier=1,      # one task at a time per worker (fair scheduling)
    task_soft_time_limit=300,          # 5 min soft limit
    task_time_limit=600,               # 10 min hard limit
    result_expires=86400,              # keep results 24 hours

    # Retry configuration
    task_max_retries=3,
    task_default_retry_delay=60,       # 1 minute between retries
)

# ── Periodic Tasks (Beat Schedule) ────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    # Sync Squad transactions every 30 minutes for all users
    "sync-all-transactions-every-30min": {
        "task": "app.workers.tasks.sync_transactions.sync_all_users_transactions",
        "schedule": crontab(minute="*/30"),
    },

    # Run fraud scan every hour
    "fraud-scan-every-hour": {
        "task": "app.workers.tasks.fraud_scan.scan_all_recent_transactions",
        "schedule": crontab(minute=0),   # top of every hour
    },

    # Send weekly summary every Monday at 9 AM (Lagos time)
    "weekly-summary-monday-9am": {
        "task": "app.workers.tasks.alert_tasks.send_weekly_summaries",
        "schedule": crontab(hour=9, minute=0, day_of_week="monday"),
    },

    # Refresh forecasts daily at 6 AM
    "refresh-forecasts-6am": {
        "task": "app.workers.tasks.forecast_tasks.refresh_all_forecasts",
        "schedule": crontab(hour=6, minute=0),
    },
}
