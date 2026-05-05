"""
SquadMind – FraudLog Model
Detailed record of every fraud flag: which rules fired, confidence score, resolution.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class FraudLog(Base):
    __tablename__ = "fraud_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Detection Details ─────────────────────────────────────────────────────
    rules_triggered: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g. ["large_amount", "night_transaction", "velocity_breach"]

    risk_score: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=2), nullable=False
    )  # 0.00 – 100.00

    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    # low | medium | high | critical

    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Human-readable explanation (AI-generated or rule-based)

    # ── Resolution ────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False, index=True)
    # open | investigating | resolved_genuine | resolved_fraud | dismissed

    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="fraud_logs")  # noqa: F821
    transaction: Mapped["Transaction"] = relationship(  # noqa: F821
        "Transaction", back_populates="fraud_logs"
    )
