"""
SquadMind – Forecast Model
Stores cash-flow forecast results per user per run.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Forecast Metadata ─────────────────────────────────────────────────────
    forecast_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    algorithm: Mapped[str] = mapped_column(String(100), nullable=False, default="moving_average")
    # moving_average | weighted_ma | trend_adjusted

    # ── Summary Figures ───────────────────────────────────────────────────────
    projected_revenue: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    projected_expenses: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    projected_net: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )  # 0–100; higher = more data / stable trend

    # ── Full Daily Breakdown ──────────────────────────────────────────────────
    daily_projections: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # { "2025-01-01": {"revenue": 50000, "expenses": 20000, "net": 30000}, ... }

    # ── AI Narrative ──────────────────────────────────────────────────────────
    ai_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Plain-English or Pidgin explanation of the forecast

    # ── Lookback Window ───────────────────────────────────────────────────────
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    transaction_count_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    user: Mapped["User"] = relationship("User", back_populates="forecasts")  # noqa: F821
