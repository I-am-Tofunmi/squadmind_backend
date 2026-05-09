"""
SquadMind – TrustScore Service
Calculates business creditworthiness using transaction behavior,
fraud intelligence, forecasting confidence, and alert patterns.
"""

from __future__ import annotations

from app.schemas.trust_score import (
    TrustScoreBreakdown,
    TrustScoreResponse,
)


def calculate_trust_score() -> TrustScoreResponse:
    """
    Temporary production-safe TrustScore engine.

    Phase 1:
    Uses controlled logic + existing tested backend behavior.

    Later:
    This can be upgraded to pull directly from:
    - transactions summary
    - fraud logs
    - forecasts
    - alerts
    """

    # Current demo score based on your tested backend
    revenue_stability = 18
    fraud_risk = 14
    forecast_confidence = 8
    payment_success_rate = 11
    customer_consistency = 7
    smart_alert_risk = 8

    total_score = (
        revenue_stability
        + fraud_risk
        + forecast_confidence
        + payment_success_rate
        + customer_consistency
        + smart_alert_risk
    )

    # Grade logic
    if total_score >= 85:
        grade = "A"
        label = "Credit Ready"
        ai_summary = "Business is highly creditworthy and ready for strong lending support."
        pidgin_summary = "Your business strong well-well. Lender fit trust you fast."

    elif total_score >= 70:
        grade = "B"
        label = "Strong"
        ai_summary = "Business shows strong lending confidence with low operational risk."
        pidgin_summary = "Your business strong and stable. Credit fit land easily."

    elif total_score >= 55:
        grade = "C+"
        label = "Moderate Lending Confidence"
        ai_summary = "Business is eligible for controlled lending with monitoring."
        pidgin_summary = "Your business dey okay, but lender go still watch am small."

    elif total_score >= 40:
        grade = "D"
        label = "High Risk"
        ai_summary = "Business needs operational improvement before strong lending confidence."
        pidgin_summary = "Your business still get risk. Need better structure first."

    else:
        grade = "F"
        label = "Unsafe"
        ai_summary = "Business currently shows unsafe lending conditions."
        pidgin_summary = "Right now, lender no go trust this business easily."

    return TrustScoreResponse(
        score=total_score,
        grade=grade,
        label=label,
        breakdown=TrustScoreBreakdown(
            revenue_stability=revenue_stability,
            fraud_risk=fraud_risk,
            forecast_confidence=forecast_confidence,
            payment_success_rate=payment_success_rate,
            customer_consistency=customer_consistency,
            smart_alert_risk=smart_alert_risk,
        ),
        ai_summary=ai_summary,
        pidgin_summary=pidgin_summary,
    )