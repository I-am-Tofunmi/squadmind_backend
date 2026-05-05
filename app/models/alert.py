"""
SquadMind – Alert Model
Stores smart alerts dispatched via WhatsApp / SMS / Email.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. fraud_detected | large_transaction | low_balance | weekly_summary | anomaly

    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    # whatsapp | sms | email

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)  # phone or email

    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)
    # pending | sent | delivered | failed

    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)   # provider response
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="alerts")  # noqa: F821
