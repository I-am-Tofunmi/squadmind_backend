"""
SquadMind – Alerts Router  /api/v1/alerts
WhatsApp, SMS, and Email notification management.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select

from app.api.deps import CurrentUser, DB
from app.core.logging import get_logger
from app.models.alert import Alert
from app.schemas.dashboard import AlertResponse
from app.utils.responses import success_response

log = get_logger(__name__)
router = APIRouter(prefix="/alerts", tags=["Smart Alerts"])


class SendTestAlertRequest(BaseModel):
    channel: str       # whatsapp | sms | email
    message: str = "This is a test alert from SquadMind AI 🚀"


@router.get("/", response_model=dict, summary="List all alerts")
async def list_alerts(
    current_user: CurrentUser,
    db: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    alert_type: Optional[str] = None,
    channel: Optional[str] = Query(None, enum=["whatsapp", "sms", "email"]),
    status: Optional[str] = Query(None, enum=["pending", "sent", "delivered", "failed"]),
) -> dict:
    filters = [Alert.user_id == current_user.id]
    if alert_type:
        filters.append(Alert.alert_type == alert_type)
    if channel:
        filters.append(Alert.channel == channel)
    if status:
        filters.append(Alert.status == status)

    count_q = await db.execute(select(func.count()).where(and_(*filters)))
    total = count_q.scalar() or 0

    result = await db.execute(
        select(Alert)
        .where(and_(*filters))
        .order_by(Alert.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return success_response(
        data={
            "items": [AlertResponse.model_validate(a).model_dump(mode="json") for a in result.scalars().all()],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    )


@router.post(
    "/test",
    response_model=dict,
    summary="Send a test alert to yourself",
)
async def send_test_alert(
    payload: SendTestAlertRequest,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """
    Sends a test notification so the user can verify their channel works.
    """
    from app.services.alert_service import AlertService

    alert_service = AlertService(db)
    result = await alert_service.send_alert(
        user=current_user,
        alert_type="test",
        channel=payload.channel,
        title="SquadMind Test Alert",
        message=payload.message,
    )

    return success_response(
        data=result,
        message=f"Test alert sent via {payload.channel}!",
    )


@router.get("/preferences", response_model=dict, summary="Get alert preferences")
async def get_preferences(current_user: CurrentUser) -> dict:
    return success_response(
        data={
            "whatsapp_enabled": current_user.whatsapp_enabled,
            "sms_enabled": current_user.sms_enabled,
            "email_alerts_enabled": current_user.email_alerts_enabled,
            "alert_phone": current_user.alert_phone,
            "email": current_user.email,
        }
    )
