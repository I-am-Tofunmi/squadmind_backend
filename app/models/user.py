"""
SquadMind – User Model
Stores SME business accounts + their Squad API credentials.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    # ── Primary Key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )

    # ── Business Info ─────────────────────────────────────────────────────────
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Auth ──────────────────────────────────────────────────────────────────
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Squad API Integration ─────────────────────────────────────────────────
    squad_secret_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    squad_public_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    squad_merchant_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    squad_last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Notification Preferences ──────────────────────────────────────────────
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    email_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        "Transaction", back_populates="user", lazy="select"
    )
    alerts: Mapped[list["Alert"]] = relationship(  # noqa: F821
        "Alert", back_populates="user", lazy="select"
    )
    fraud_logs: Mapped[list["FraudLog"]] = relationship(  # noqa: F821
        "FraudLog", back_populates="user", lazy="select"
    )
    forecasts: Mapped[list["Forecast"]] = relationship(  # noqa: F821
        "Forecast", back_populates="user", lazy="select"
    )

    @property
    def has_squad_credentials(self) -> bool:
        return bool(self.squad_secret_key and self.squad_public_key)
