"""
SquadMind – Forecast Service
Moving average + trend-adjusted cash flow projection.
No heavy ML — fast, explainable, and demo-ready.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.forecast import Forecast
from app.models.transaction import Transaction

log = get_logger(__name__)


class ForecastService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate(
        self,
        user_id: UUID,
        days_ahead: int = 30,
        algorithm: str = "moving_average",
        with_pidgin: bool = True,
    ) -> Forecast:
        """
        Generate a cash-flow forecast and persist it.
        """
        # ── Pull historical daily revenue ─────────────────────────────────────
        lookback = settings.FORECAST_LOOKBACK_DAYS
        since = datetime.now(tz=timezone.utc) - timedelta(days=lookback)

        daily_q = await self.db.execute(
            select(
                func.date_trunc("day", Transaction.transaction_date).label("day"),
                func.sum(Transaction.amount).label("revenue"),
                func.count().label("count"),
            )
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_type == "credit",
                    Transaction.status == "success",
                    Transaction.transaction_date >= since,
                )
            )
            .group_by("day")
            .order_by("day")
        )
        daily_rows = daily_q.all()

        if not daily_rows:
            # No data — return a zero forecast
            return await self._save_forecast(
                user_id=user_id,
                days_ahead=days_ahead,
                algorithm=algorithm,
                projected_revenue=Decimal("0"),
                projected_net=Decimal("0"),
                confidence_score=Decimal("0"),
                daily_projections={},
                transaction_count=0,
                lookback=lookback,
                narrative="No transaction data available yet. Connect your Squad API and sync transactions to get your first forecast.",
                pidgin="No data yet, abeg connect your Squad API make we see your money movement!",
            )

        daily_values = [float(row.revenue) for row in daily_rows]
        tx_count = sum(row.count for row in daily_rows)

        # ── Choose algorithm ──────────────────────────────────────────────────
        if algorithm == "weighted_ma":
            projected_daily = self._weighted_moving_average(daily_values, days_ahead)
        elif algorithm == "trend_adjusted":
            projected_daily = self._trend_adjusted(daily_values, days_ahead)
        else:
            projected_daily = self._simple_moving_average(daily_values, days_ahead)

        # ── Build daily projections dict ──────────────────────────────────────
        today = datetime.now(tz=timezone.utc).date()
        daily_projections: Dict[str, Any] = {}
        total_projected = 0.0

        for i, rev in enumerate(projected_daily):
            date_key = (today + timedelta(days=i + 1)).isoformat()
            estimated_expenses = rev * 0.35   # 35% expense ratio assumption
            net = rev - estimated_expenses
            daily_projections[date_key] = {
                "revenue": round(rev, 2),
                "expenses": round(estimated_expenses, 2),
                "net": round(net, 2),
            }
            total_projected += rev

        # ── Confidence score: more data + stable trend = higher confidence ────
        data_confidence = min(100, len(daily_values) / lookback * 100)
        volatility = self._coefficient_of_variation(daily_values)
        stability_score = max(0, 100 - volatility * 100)
        confidence = round((data_confidence * 0.6) + (stability_score * 0.4), 2)

        projected_expenses = total_projected * 0.35
        projected_net = total_projected - projected_expenses

        # ── AI narrative ──────────────────────────────────────────────────────
        avg_daily = sum(daily_values) / len(daily_values)
        narrative = (
            f"Based on {len(daily_values)} days of transaction history, your average daily revenue is ₦{avg_daily:,.0f}. "
            f"Over the next {days_ahead} days, SquadMind projects total revenue of ₦{total_projected:,.0f} "
            f"with an estimated net income of ₦{projected_net:,.0f} (after 35% operating expense assumption). "
            f"Confidence level: {confidence:.0f}%. "
            + ("The trend is positive — keep scaling!" if projected_daily[-1] > projected_daily[0] else "Revenue shows a slight decline — review customer retention.")
        )

        pidgin = (
            f"Bros, we don look your last {len(daily_values)} days — your daily revenue dey average ₦{avg_daily:,.0f}. "
            f"For the next {days_ahead} days, e go reach ₦{total_projected:,.0f} total. "
            f"After expenses, your net go be around ₦{projected_net:,.0f}. "
            + ("Your money dey grow — e don do! 🚀" if projected_daily[-1] > projected_daily[0] else "Revenue small slow down — time to hustle more! 💪")
        )

        return await self._save_forecast(
            user_id=user_id,
            days_ahead=days_ahead,
            algorithm=algorithm,
            projected_revenue=Decimal(str(round(total_projected, 2))),
            projected_net=Decimal(str(round(projected_net, 2))),
            confidence_score=Decimal(str(confidence)),
            daily_projections=daily_projections,
            transaction_count=tx_count,
            lookback=lookback,
            narrative=narrative if not with_pidgin else narrative,
            pidgin=pidgin,
        )

    def _simple_moving_average(self, values: List[float], periods_ahead: int) -> List[float]:
        """N-period simple moving average extrapolated forward."""
        window = min(7, len(values))
        avg = sum(values[-window:]) / window
        return [avg] * periods_ahead

    def _weighted_moving_average(self, values: List[float], periods_ahead: int) -> List[float]:
        """Linearly weighted moving average — recent days count more."""
        window = min(14, len(values))
        recent = values[-window:]
        weights = list(range(1, len(recent) + 1))
        wma = sum(v * w for v, w in zip(recent, weights)) / sum(weights)
        return [wma] * periods_ahead

    def _trend_adjusted(self, values: List[float], periods_ahead: int) -> List[float]:
        """
        Linear trend (least squares) extrapolated forward.
        Slightly dampened so we don't over-project.
        """
        n = len(values)
        if n < 3:
            return self._simple_moving_average(values, periods_ahead)

        x_mean = (n - 1) / 2
        y_mean = sum(values) / n

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        slope = numerator / denominator if denominator else 0
        intercept = y_mean - slope * x_mean

        # Dampen slope by 30% to be conservative
        slope *= 0.7

        projections = []
        for step in range(1, periods_ahead + 1):
            projected = intercept + slope * (n - 1 + step)
            projections.append(max(0, projected))   # floor at 0

        return projections

    @staticmethod
    def _coefficient_of_variation(values: List[float]) -> float:
        """Volatility metric: std_dev / mean. Lower = more stable."""
        if not values or sum(values) == 0:
            return 1.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = variance ** 0.5
        return std_dev / mean if mean else 1.0

    async def _save_forecast(
        self,
        user_id: UUID,
        days_ahead: int,
        algorithm: str,
        projected_revenue: Decimal,
        projected_net: Decimal,
        confidence_score: Decimal,
        daily_projections: Dict,
        transaction_count: int,
        lookback: int,
        narrative: str,
        pidgin: str,
    ) -> Forecast:
        full_narrative = f"{narrative}\n\n🇳🇬 Pidgin:\n{pidgin}"

        forecast = Forecast(
            user_id=user_id,
            forecast_period_days=days_ahead,
            algorithm=algorithm,
            projected_revenue=projected_revenue,
            projected_expenses=projected_revenue - projected_net,
            projected_net=projected_net,
            confidence_score=confidence_score,
            daily_projections=daily_projections,
            ai_narrative=full_narrative,
            lookback_days=lookback,
            transaction_count_used=transaction_count,
        )
        self.db.add(forecast)
        await self.db.flush()

        log.info(
            "forecast_generated",
            user_id=str(user_id),
            days_ahead=days_ahead,
            projected_revenue=float(projected_revenue),
            confidence=float(confidence_score),
        )

        return forecast
