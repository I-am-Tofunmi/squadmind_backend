"""
SquadMind – TrustScore Schemas
Creditworthiness scoring for SMEs using behavioral financial intelligence.
"""

from __future__ import annotations

from typing import Dict

from pydantic import BaseModel


class TrustScoreBreakdown(BaseModel):
    revenue_stability: int
    fraud_risk: int
    forecast_confidence: int
    payment_success_rate: int
    customer_consistency: int
    smart_alert_risk: int


class TrustScoreResponse(BaseModel):
    score: int
    grade: str
    label: str
    breakdown: TrustScoreBreakdown
    ai_summary: str
    pidgin_summary: str

    model_config = {
        "from_attributes": True
    }