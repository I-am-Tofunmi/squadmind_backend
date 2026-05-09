"""
SquadMind – Dashboard Schemas
The main payload the frontend Revenue Intelligence Dashboard consumes.
Designed to give the React dashboard everything it needs in ONE request.
"""

from __future__ import annotations
from uuid import UUID

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ── Metric Cards ──────────────────────────────────────────────────────────────
class MetricCard(BaseModel):
    label: str
    value: str              # formatted string e.g. "₦4,200,000"
    raw_value: Decimal
    change_percent: float   # vs previous period; positive = growth
    trend: str              # "up" | "down" | "flat"


# ── Health Score ──────────────────────────────────────────────────────────────
class HealthScore(BaseModel):
    score: int              # 0–100
    grade: str              # A | B | C | D | F
    label: str              # "Excellent" | "Good" | "Fair" | "Poor" | "Critical"
    breakdown: Dict[str, int]   # {"revenue_consistency": 85, "fraud_rate": 95, ...}
    ai_summary: str         # 1-sentence plain-English summary
    pidgin_summary: str     # Pidgin version: "Bros, your money dey flow well..."


# ── Revenue Chart (for sparklines / area charts) ──────────────────────────────
class RevenueDataPoint(BaseModel):
    date: str               # "2025-01-15"
    revenue: Decimal
    transactions: int


# ── Customer Insights ─────────────────────────────────────────────────────────
class TopCustomer(BaseModel):
    customer_id: Optional[str]
    customer_name: Optional[str]
    total_spend: Decimal
    transaction_count: int
    last_transaction_date: Optional[datetime]


# ── Fraud Summary ──────────────────────────────────────────────────────────────
class FraudSummary(BaseModel):
    flagged_count: int
    flagged_amount: Decimal
    fraud_rate_percent: float
    open_cases: int
    recent_flags: List[Dict[str, Any]]


# ── Alert Summary ──────────────────────────────────────────────────────────────
class AlertSummary(BaseModel):
    unread_count: int
    recent: List[Dict[str, Any]]


# ── Main Dashboard Response ───────────────────────────────────────────────────
class DashboardResponse(BaseModel):
    """
    Single endpoint payload for the main dashboard.
    Reduces round-trips from the React frontend.
    """
    user_id: str
    business_name: str
    period: str             # "last_30_days" | "last_7_days" | "this_month"
    generated_at: datetime
    has_squad_credentials: bool
    squad_last_synced_at: Optional[datetime]

    # KPI cards
    metrics: List[MetricCard]

    # Health score
    health_score: HealthScore

    # Revenue chart data
    revenue_trend: List[RevenueDataPoint]

    # Customer analytics
    top_customers: List[TopCustomer]
    unique_customers: int
    returning_customer_rate: float

    # Fraud
    fraud_summary: FraudSummary

    # Alerts
    alert_summary: AlertSummary

    # AI-generated insight (plain English / Pidgin toggle)
    ai_insight: str
    ai_insight_pidgin: str

    # Is this live data or mock?
    is_mock_data: bool = False


# ── Schemas for fraud and alerts ──────────────────────────────────────────────
class FraudLogResponse(BaseModel):
    id: UUID
    transaction_id: Optional[UUID]
    risk_score: Decimal
    risk_level: str
    rules_triggered: Optional[List[str]]
    explanation: Optional[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertResponse(BaseModel):
    id: str
    alert_type: str
    channel: str
    title: str
    message: str
    status: str
    sent_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ForecastResponse(BaseModel):
    id: UUID
    forecast_period_days: int
    projected_revenue: Decimal
    projected_net: Decimal
    confidence_score: Decimal
    algorithm: str
    daily_projections: Optional[Dict[str, Any]]
    ai_narrative: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
