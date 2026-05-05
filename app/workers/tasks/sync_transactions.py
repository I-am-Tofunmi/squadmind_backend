"""
SquadMind – Transaction Sync Task
Pulls transactions from Squad API and upserts them into PostgreSQL.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import get_db_context
from app.db.redis import cache
from app.models.transaction import Transaction
from app.models.user import User
from app.services.squad_service import SquadService, normalise_squad_transaction
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.sync_transactions.sync_user_transactions_task",
    max_retries=3,
    default_retry_delay=60,
)
def sync_user_transactions_task(self, user_id: str) -> dict:
    """
    Celery task: sync Squad transactions for a single user.
    Called manually from the /transactions/sync endpoint.
    """
    return asyncio.get_event_loop().run_until_complete(
        _sync_user(self, user_id)
    )


async def _sync_user(task, user_id: str) -> dict:
    """Async core of the sync — runs inside a fresh event loop."""
    logger.info(f"Starting transaction sync for user {user_id}")

    async with get_db_context() as db:
        # Fetch user with Squad credentials
        result = await db.execute(select(User).where(User.id == UUID(user_id)))
        user = result.scalar_one_or_none()

        if not user:
            return {"status": "error", "error": "User not found"}

        if not user.has_squad_credentials:
            return {"status": "error", "error": "No Squad credentials configured"}

        squad = SquadService(user)

        try:
            raw_transactions = await squad.get_all_transactions(lookback_days=90)
        except Exception as e:
            logger.error(f"Squad API fetch failed for user {user_id}: {e}")
            try:
                raise task.retry(exc=e)
            except Exception:
                return {"status": "error", "error": str(e)}

        # Upsert transactions
        synced_count = 0
        skipped_count = 0

        for raw_tx in raw_transactions:
            try:
                normalised = normalise_squad_transaction(raw_tx, user_id)
                ref = normalised.get("squad_transaction_ref")

                if ref:
                    # Check for existing transaction
                    existing = await db.execute(
                        select(Transaction).where(Transaction.squad_transaction_ref == ref)
                    )
                    if existing.scalar_one_or_none():
                        skipped_count += 1
                        continue

                tx = Transaction(**normalised)
                db.add(tx)
                synced_count += 1

            except Exception as e:
                logger.warning(f"Failed to process transaction: {e}, raw: {raw_tx.get('transaction_ref')}")
                continue

        # Update user's last sync timestamp
        user.squad_last_synced_at = datetime.now(tz=timezone.utc)

        # Invalidate dashboard cache
        await cache.delete_pattern(f"dashboard:{user_id}:*")

        logger.info(
            f"Sync complete for {user_id}: {synced_count} synced, {skipped_count} skipped"
        )

        return {
            "status": "success",
            "user_id": user_id,
            "synced": synced_count,
            "skipped": skipped_count,
            "total_fetched": len(raw_transactions),
        }


@celery_app.task(name="app.workers.tasks.sync_transactions.sync_all_users_transactions")
def sync_all_users_transactions() -> dict:
    """
    Periodic task: sync transactions for ALL users with Squad credentials.
    Runs every 30 minutes via Celery Beat.
    """
    return asyncio.get_event_loop().run_until_complete(_sync_all())


async def _sync_all() -> dict:
    """Async core: fetch all eligible users and queue individual sync tasks."""
    async with get_db_context() as db:
        result = await db.execute(
            select(User).where(
                User.is_active == True,  # noqa: E712
                User.squad_secret_key.isnot(None),
            )
        )
        users = result.scalars().all()

    logger.info(f"Queuing sync for {len(users)} users")

    for user in users:
        sync_user_transactions_task.delay(str(user.id))

    return {"queued": len(users)}
