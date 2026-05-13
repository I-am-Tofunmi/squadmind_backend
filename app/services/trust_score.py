"""
SquadMind – Dynamic TrustScore Service
Calculates business creditworthiness from real transaction behavior.
"""

from __future__ import annotations

from decimal import Decimal
from statistics import mean

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.schemas.trust_score import (
    TrustScoreBreakdown,
    TrustScoreResponse,
)


async def calculate_trust_score(
    db: AsyncSession,
    user_id,
) -> TrustScoreResponse:
    """
    Dynamic TrustScore engine using real transaction behavior.

    Scoring Factors:
    - Revenue Stability
    - Fraud Risk
    - Payment Success Rate
    - Customer Consistency
    - Forecast Confidence (temporary controlled score)
    - Smart Alert Risk (temporary controlled score)
    """

    result = await db.execute(
        select(Transaction).where(Transaction.user_id == user_id)
    )
    transactions = result.scalars().all()

    if not transactions:
        return TrustScoreResponse(
            score=20,
            grade="F",
            label="Insufficient History",
            breakdown=TrustScoreBreakdown(
                revenue_stability=5,
                fraud_risk=5,
                forecast_confidence=3,
                payment_success_rate=3,
                customer_consistency=2,
                smart_alert_risk=2,
            ),
            ai_summary="Not enough transaction history to determine lending confidence.",
            pidgin_summary="No enough transaction history yet. Make more business transactions first.",
        )

    total_amount = sum(float(t.amount) for t in transactions)
    avg_amount = total_amount / len(transactions)

    success_count = sum(1 for t in transactions if t.status == "success")
    success_rate = (success_count / len(transactions)) * 100

    avg_fraud_score = mean(
        [float(t.fraud_score or 0) for t in transactions]
    )

    unique_customers = len(
        set(t.customer_email for t in transactions if t.customer_email)
    )

    # Revenue Stability (20)
    if avg_amount >= 150000:
        revenue_stability = 20
    elif avg_amount >= 80000:
        revenue_stability = 15
    else:
        revenue_stability = 8

    # Fraud Risk (15)
    if avg_fraud_score <= 20:
        fraud_risk = 15
    elif avg_fraud_score <= 35:
        fraud_risk = 10
    else:
        fraud_risk = 5

    # Payment Success Rate (15)
    if success_rate >= 80:
        payment_success_rate = 15
    elif success_rate >= 60:
        payment_success_rate = 10
    else:
        payment_success_rate = 5

    # Customer Consistency (10)
    if unique_customers >= 8:
        customer_consistency = 10
    elif unique_customers >= 5:
        customer_consistency = 7
    else:
        customer_consistency = 4

    # Controlled temporary values
    forecast_confidence = 8
    smart_alert_risk = 8

    total_score = (
        revenue_stability
        + fraud_risk
        + payment_success_rate
        + customer_consistency
        + forecast_confidence
        + smart_alert_risk
    )

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