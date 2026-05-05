"""
SquadMind – Fraud Scan Task
Periodic background fraud detection sweep.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from celery.utils.log import get_task_logger

from app.db.session import get_db_context
from app.models.user import User
from app.services.fraud_service import scan_recent_transactions
from app.workers.celery_app import celery_app
from sqlalchemy import select

logger = get_task_logger(__name__)


@celery_app.task(name="app.workers.tasks.fraud_scan.scan_all_recent_transactions")
def scan_all_recent_transactions() -> dict:
    """Periodic: run fraud scan for all active users over last 24h."""
    return asyncio.get_event_loop().run_until_complete(_scan_all())


async def _scan_all() -> dict:
    async with get_db_context() as db:
        result = await db.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = result.scalars().all()

        total_flagged = 0
        for user in users:
            try:
                flagged = await scan_recent_transactions(db, user.id, hours=24)
                total_flagged += flagged
            except Exception as e:
                logger.error(f"Fraud scan failed for user {user.id}: {e}")

    return {"users_scanned": len(users), "total_flagged": total_flagged}
