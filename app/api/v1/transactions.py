"""
SquadMind – Transactions Router  /api/v1/transactions
Transaction listing, filtering, sync trigger, and analytics summaries.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import and_, func, select

from app.api.deps import CurrentUser, DB, SquadUser
from app.core.logging import get_logger
from app.db.redis import cache
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionListResponse, TransactionResponse, TransactionSummary
from app.utils.formatters import format_naira
from app.utils.responses import success_response

log = get_logger(__name__)
router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get(
    "/",
    response_model=dict,
    summary="List transactions with filters and pagination",
)
async def list_transactions(
    current_user: CurrentUser,
    db: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    transaction_type: Optional[str] = Query(None, enum=["credit", "debit", "transfer", "payment"]),
    status: Optional[str] = Query(None, enum=["success", "pending", "failed", "reversed"]),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    flagged_only: bool = False,
    search: Optional[str] = Query(None, description="Search by customer name, email, or ref"),
) -> dict:
    """
    Paginated transaction list with rich filtering.
    Frontend uses this for the transaction table with filter panels.
    """
    filters = [Transaction.user_id == current_user.id]

    if transaction_type:
        filters.append(Transaction.transaction_type == transaction_type)
    if status:
        filters.append(Transaction.status == status)
    if start_date:
        filters.append(Transaction.transaction_date >= start_date)
    if end_date:
        filters.append(Transaction.transaction_date <= end_date)
    if min_amount is not None:
        filters.append(Transaction.amount >= min_amount)
    if max_amount is not None:
        filters.append(Transaction.amount <= max_amount)
    if flagged_only:
        filters.append(Transaction.is_flagged_fraud == True)  # noqa: E712
    if search:
        from sqlalchemy import or_
        filters.append(
            or_(
                Transaction.customer_name.ilike(f"%{search}%"),
                Transaction.customer_email.ilike(f"%{search}%"),
                Transaction.squad_transaction_ref.ilike(f"%{search}%"),
            )
        )

    # Count
    count_q = await db.execute(select(func.count()).where(and_(*filters)))
    total = count_q.scalar() or 0

    # Fetch page
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Transaction)
        .where(and_(*filters))
        .order_by(Transaction.transaction_date.desc())
        .offset(offset)
        .limit(page_size)
    )
    transactions = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size

    return success_response(
        data={
            "items": [TransactionResponse.model_validate(t).model_dump(mode="json") for t in transactions],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    )


@router.get(
    "/summary",
    response_model=dict,
    summary="Transaction analytics summary for a date range",
)
async def get_transaction_summary(
    current_user: CurrentUser,
    db: DB,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """
    Aggregated stats: revenue, success rate, channel breakdown, daily trend.
    Used by analytics cards on the dashboard.
    """
    now = datetime.now(tz=timezone.utc)
    if not start_date:
        start_date = now - timedelta(days=30)
    if not end_date:
        end_date = now

    base_filters = [
        Transaction.user_id == current_user.id,
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date <= end_date,
    ]

    # Overall aggregates
    agg_q = await db.execute(
        select(
            func.count().label("total"),
            func.coalesce(func.sum(Transaction.amount), 0).label("revenue"),
            func.coalesce(func.max(Transaction.amount), 0).label("largest"),
            func.coalesce(func.avg(Transaction.amount), 0).label("average"),
        ).where(and_(*base_filters))
    )
    agg = agg_q.one()

    # Status breakdown
    status_q = await db.execute(
        select(Transaction.status, func.count().label("cnt"))
        .where(and_(*base_filters))
        .group_by(Transaction.status)
    )
    status_breakdown = {row.status: row.cnt for row in status_q.all()}

    # Channel breakdown
    channel_q = await db.execute(
        select(Transaction.payment_channel, func.count().label("cnt"))
        .where(and_(*base_filters))
        .group_by(Transaction.payment_channel)
    )
    channel_breakdown = {(row.payment_channel or "unknown"): row.cnt for row in channel_q.all()}

    # Daily trend
    trend_q = await db.execute(
        select(
            func.date_trunc("day", Transaction.transaction_date).label("day"),
            func.sum(Transaction.amount).label("amount"),
            func.count().label("count"),
        )
        .where(and_(*base_filters))
        .group_by("day")
        .order_by("day")
    )
    daily_trend = [
        {
            "date": row.day.strftime("%Y-%m-%d"),
            "amount": float(row.amount),
            "count": row.count,
        }
        for row in trend_q.all()
    ]

    return success_response(
        data={
            "total_revenue": float(agg.revenue),
            "total_revenue_formatted": format_naira(Decimal(str(agg.revenue))),
            "total_transactions": agg.total,
            "successful_transactions": status_breakdown.get("success", 0),
            "failed_transactions": status_breakdown.get("failed", 0),
            "average_transaction_value": float(agg.average),
            "largest_transaction": float(agg.largest),
            "success_rate": round(
                status_breakdown.get("success", 0) / agg.total * 100 if agg.total else 0, 2
            ),
            "payment_channel_breakdown": channel_breakdown,
            "daily_trend": daily_trend,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
        }
    )


@router.post(
    "/sync",
    response_model=dict,
    summary="Trigger Squad API transaction sync",
)
async def sync_transactions(
    current_user: SquadUser,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Kick off a background sync of Squad API transactions.
    Returns immediately; frontend can poll /sync/status.
    """
    from app.workers.tasks.sync_transactions import sync_user_transactions_task

    # Queue the Celery task
    task = sync_user_transactions_task.delay(str(current_user.id))

    log.info("transaction_sync_triggered", user_id=str(current_user.id), task_id=task.id)

    return success_response(
        data={
            "task_id": task.id,
            "status": "queued",
            "message": "Sync started. This usually takes 10–30 seconds.",
            "poll_url": f"/api/v1/transactions/sync/status/{task.id}",
        },
        message="Squad API sync initiated",
    )


@router.get(
    "/sync/status/{task_id}",
    response_model=dict,
    summary="Poll the status of a transaction sync job",
)
async def sync_status(task_id: str, current_user: CurrentUser) -> dict:
    """Check whether a background sync task has completed."""
    from app.workers.celery_app import celery_app
    task_result = celery_app.AsyncResult(task_id)

    return success_response(
        data={
            "task_id": task_id,
            "status": task_result.status,          # PENDING | STARTED | SUCCESS | FAILURE
            "result": task_result.result if task_result.ready() else None,
        }
    )


@router.get(
    "/{transaction_id}",
    response_model=dict,
    summary="Get a single transaction by ID",
)
async def get_transaction(
    transaction_id: str,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """Return a single transaction with full detail including fraud flags."""
    from uuid import UUID

    try:
        tx_uuid = UUID(transaction_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid transaction ID format")

    result = await db.execute(
        select(Transaction).where(
            and_(Transaction.id == tx_uuid, Transaction.user_id == current_user.id)
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return success_response(
        data=TransactionResponse.model_validate(tx).model_dump(mode="json")
    )
