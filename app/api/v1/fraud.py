"""
SquadMind – Fraud Detection Router  /api/v1/fraud
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, func, select

from app.api.deps import CurrentUser, DB
from app.core.logging import get_logger
from app.models.fraud_log import FraudLog
from app.models.transaction import Transaction
from app.schemas.dashboard import FraudLogResponse
from app.utils.responses import success_response

log = get_logger(__name__)
router = APIRouter(prefix="/fraud", tags=["Fraud Detection"])


@router.get("/", response_model=dict, summary="List fraud flags")
async def list_fraud_flags(
    current_user: CurrentUser,
    db: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, enum=["open", "investigating", "resolved_genuine", "resolved_fraud", "dismissed"]),
    risk_level: Optional[str] = Query(None, enum=["low", "medium", "high", "critical"]),
) -> dict:
    filters = [FraudLog.user_id == current_user.id]
    if status:
        filters.append(FraudLog.status == status)
    if risk_level:
        filters.append(FraudLog.risk_level == risk_level)

    count_q = await db.execute(select(func.count()).where(and_(*filters)))
    total = count_q.scalar() or 0

    result = await db.execute(
        select(FraudLog)
        .where(and_(*filters))
        .order_by(FraudLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = result.scalars().all()

    return success_response(
        data={
            "items": [FraudLogResponse.model_validate(f).model_dump(mode="json") for f in logs],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    )


@router.post(
    "/scan/{transaction_id}",
    response_model=dict,
    summary="Run fraud scan on a specific transaction",
)
async def scan_transaction(
    transaction_id: str,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """
    Manually trigger the fraud detection engine on a transaction.
    Useful for the 'Scan this transaction' button in the UI.
    """
    try:
        tx_uuid = UUID(transaction_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid transaction ID")

    result = await db.execute(
        select(Transaction).where(
            and_(Transaction.id == tx_uuid, Transaction.user_id == current_user.id)
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    from app.services.fraud_service import FraudDetectionService
    fraud_service = FraudDetectionService(db)
    fraud_result = await fraud_service.analyze_transaction(tx, current_user.id)

    return success_response(data=fraud_result, message="Fraud scan complete")


@router.patch(
    "/{fraud_log_id}/resolve",
    response_model=dict,
    summary="Resolve a fraud flag",
)
async def resolve_fraud_flag(
    fraud_log_id: str,
    resolution: str = Query(..., enum=["resolved_genuine", "resolved_fraud", "dismissed"]),
    note: Optional[str] = Query(None),
    current_user: CurrentUser = None,
    db: DB = None,
) -> dict:
    from datetime import datetime, timezone

    try:
        log_uuid = UUID(fraud_log_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fraud log ID")

    result = await db.execute(
        select(FraudLog).where(
            and_(FraudLog.id == log_uuid, FraudLog.user_id == current_user.id)
        )
    )
    fraud_log = result.scalar_one_or_none()
    if not fraud_log:
        raise HTTPException(status_code=404, detail="Fraud log not found")

    fraud_log.status = resolution
    fraud_log.resolution_note = note
    fraud_log.resolved_at = datetime.now(tz=timezone.utc)
    fraud_log.reviewed_by = current_user.email

    return success_response(
        data=FraudLogResponse.model_validate(fraud_log).model_dump(mode="json"),
        message=f"Fraud flag marked as {resolution}",
    )
