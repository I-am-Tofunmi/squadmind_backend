"""
SquadMind – Transaction Model
Stores normalised Squad API transaction records with analysis metadata.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    # ── Primary Key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Foreign Key ───────────────────────────────────────────────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # ── Squad API Fields ──────────────────────────────────────────────────────
    squad_transaction_ref: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    squad_merchant_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Core Transaction Data ─────────────────────────────────────────────────
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)
    transaction_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # credit | debit | transfer | payment
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="success", index=True
    )  # success | pending | failed | reversed

    # ── Payer / Payee ─────────────────────────────────────────────────────────
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # ── Payment Details ───────────────────────────────────────────────────────
    payment_channel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # e.g. card | bank_transfer | ussd | pos
    narration: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)   # raw Squad payload

    # ── Analysis Flags ────────────────────────────────────────────────────────
    is_flagged_fraud: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fraud_score: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=5, scale=2), nullable=True
    )  # 0.00 – 100.00

    # ── Timestamps ────────────────────────────────────────────────────────────
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="transactions")  # noqa: F821
    fraud_logs: Mapped[list["FraudLog"]] = relationship(  # noqa: F821
        "FraudLog", back_populates="transaction", lazy="select"
    )

    # ── Composite Indexes for Analytics Queries ───────────────────────────────
    __table_args__ = (
        Index("ix_transactions_user_date", "user_id", "transaction_date"),
        Index("ix_transactions_user_type", "user_id", "transaction_type"),
        Index("ix_transactions_user_status", "user_id", "status"),
    )
