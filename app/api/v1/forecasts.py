"""
SquadMind – Forecasting Router  /api/v1/forecasts
Cash flow projections powered by moving averages and trend analysis.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DB
from app.core.logging import get_logger
from app.models.forecast import Forecast
from app.schemas.dashboard import ForecastResponse
from app.services.forecast_service import ForecastService
from app.utils.responses import success_response
from sqlalchemy import select

log = get_logger(__name__)
router = APIRouter(prefix="/forecasts", tags=["Forecasting"])


@router.post(
    "/generate",
    response_model=dict,
    summary="Generate a new cash-flow forecast",
)
async def generate_forecast(
    current_user: CurrentUser,
    db: DB,
    days_ahead: int = Query(30, ge=7, le=90),
    algorithm: str = Query("moving_average", enum=["moving_average", "weighted_ma", "trend_adjusted"]),
    with_pidgin: bool = Query(True, description="Include Pidgin explanation in response"),
) -> dict:
    """
    Run the forecasting engine and persist the result.
    Returns projected daily revenue for the next N days.
    """
    service = ForecastService(db)
    forecast = await service.generate(
        user_id=current_user.id,
        days_ahead=days_ahead,
        algorithm=algorithm,
        with_pidgin=with_pidgin,
    )

    return success_response(
        data=ForecastResponse.model_validate(forecast).model_dump(mode="json"),
        message=f"Forecast generated for the next {days_ahead} days.",
    )


@router.get(
    "/latest",
    response_model=dict,
    summary="Get the most recent forecast",
)
async def get_latest_forecast(current_user: CurrentUser, db: DB) -> dict:
    result = await db.execute(
        select(Forecast)
        .where(Forecast.user_id == current_user.id)
        .order_by(Forecast.created_at.desc())
        .limit(1)
    )
    forecast = result.scalar_one_or_none()

    if not forecast:
        # Return a mock forecast for demo
        return success_response(
            data={
                "id": "mock",
                "forecast_period_days": 30,
                "projected_revenue": 4500000,
                "projected_net": 3200000,
                "confidence_score": 72.5,
                "algorithm": "moving_average",
                "ai_narrative": "Based on your last 90 days, revenue is trending upward by about ₦50,000/day.",
                "daily_projections": {},
                "is_mock": True,
            },
            message="No forecast data yet — connect Squad API and sync transactions first.",
        )

    return success_response(
        data=ForecastResponse.model_validate(forecast).model_dump(mode="json")
    )


@router.get(
    "/history",
    response_model=dict,
    summary="List past forecasts",
)
async def list_forecasts(
    current_user: CurrentUser,
    db: DB,
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    result = await db.execute(
        select(Forecast)
        .where(Forecast.user_id == current_user.id)
        .order_by(Forecast.created_at.desc())
        .limit(limit)
    )
    forecasts = result.scalars().all()

    return success_response(
        data=[ForecastResponse.model_validate(f).model_dump(mode="json") for f in forecasts]
    )
