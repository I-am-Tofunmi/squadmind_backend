"""
SquadMind – Transaction Schemas
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TransactionResponse(BaseModel):
    id: UUID
    squad_transaction_ref: Optional[str]
    amount: Decimal
    currency: str
    transaction_type: str
    status: str
    customer_name: Optional[str]
    customer_email: Optional[str]
    payment_channel: Optional[str]
    narration: Optional[str]
    is_flagged_fraud: bool
    fraud_score: Optional[Decimal]
    transaction_date: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    items: List[TransactionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TransactionFilterParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    transaction_type: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    flagged_only: bool = False


class TransactionSummary(BaseModel):
    total_revenue: Decimal
    total_transactions: int
    successful_transactions: int
    failed_transactions: int
    average_transaction_value: Decimal
    largest_transaction: Decimal
    payment_channel_breakdown: Dict[str, int]
    daily_trend: List[Dict[str, Any]]   # [{"date": "2025-01-01", "amount": 50000, "count": 12}]
