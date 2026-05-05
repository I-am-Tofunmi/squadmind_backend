"""SquadMind – Weekly Summary Alert Task"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from celery.utils.log import get_task_logger
from sqlalchemy import and_, func, select

from app.db.session import get_db_context
from app.models.transaction import Transaction
from app.models.user import User
from app.services.alert_service import AlertService
from app.utils.formatters import format_naira
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(name="app.workers.tasks.alert_tasks.send_weekly_summaries")
def send_weekly_summaries() -> dict:
    return asyncio.get_event_loop().run_until_complete(_send_summaries())


async def _send_summaries() -> dict:
    now = datetime.now(tz=timezone.utc)
    week_start = now - timedelta(days=7)
    sent = 0

    async with get_db_context() as db:
        result = await db.execute(
            select(User).where(User.is_active == True)  # noqa
        )
        users = result.scalars().all()

        for user in users:
            try:
                # Get weekly revenue
                rev_q = await db.execute(
                    select(
                        func.coalesce(func.sum(Transaction.amount), 0).label("total"),
                        func.count().label("count"),
                    ).where(
                        and_(
                            Transaction.user_id == user.id,
                            Transaction.transaction_type == "credit",
                            Transaction.status == "success",
                            Transaction.transaction_date >= week_start,
                        )
                    )
                )
                row = rev_q.one()
                revenue = Decimal(str(row.total))
                tx_count = row.count

                message = (
                    f"📊 *Weekly Financial Summary*\n\n"
                    f"Revenue: {format_naira(revenue)}\n"
                    f"Transactions: {tx_count:,}\n"
                    f"Period: Last 7 days\n\n"
                    f"Login to SquadMind for full insights and AI analysis."
                )

                service = AlertService(db)
                for channel in ["whatsapp", "email"]:
                    await service.send_alert(
                        user=user,
                        alert_type="weekly_summary",
                        channel=channel,
                        title=f"Weekly Summary – {format_naira(revenue)}",
                        message=message,
                    )
                sent += 1

            except Exception as e:
                logger.error(f"Weekly summary failed for {user.id}: {e}")

    return {"sent": sent, "total_users": len(users)}
