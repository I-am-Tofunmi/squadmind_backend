"""SquadMind – Forecast Refresh Task"""

from __future__ import annotations

import asyncio
from sqlalchemy import select
from celery.utils.log import get_task_logger

from app.db.session import get_db_context
from app.models.user import User
from app.services.forecast_service import ForecastService
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(name="app.workers.tasks.forecast_tasks.refresh_all_forecasts")
def refresh_all_forecasts() -> dict:
    return asyncio.get_event_loop().run_until_complete(_refresh_all())


async def _refresh_all() -> dict:
    async with get_db_context() as db:
        result = await db.execute(
            select(User).where(User.is_active == True, User.squad_secret_key.isnot(None))  # noqa
        )
        users = result.scalars().all()
        refreshed = 0

        for user in users:
            try:
                service = ForecastService(db)
                await service.generate(user_id=user.id)
                refreshed += 1
            except Exception as e:
                logger.error(f"Forecast refresh failed for {user.id}: {e}")

    return {"refreshed": refreshed, "total_users": len(users)}
