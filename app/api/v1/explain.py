"""
SquadMind – AI Explanation Router  /api/v1/explain
Converts raw financial data into CFO-quality narrative explanations.
Every endpoint returns plain-English + Pidgin versions with actions.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import CurrentUser, DB
from app.core.logging import get_logger
from app.services.ai_explanation_service import AIExplanationService
from app.utils.responses import success_response

log = get_logger(__name__)
router = APIRouter(prefix="/explain", tags=["AI Explanations"])


# ── 1. Explain a fraud alert ──────────────────────────────────────────────────
@router.get(
    "/fraud/{fraud_log_id}",
    response_model=dict,
    summary="Get CFO-quality explanation for a fraud alert",
)
async def explain_fraud_alert(
    fraud_log_id: str,
    current_user: CurrentUser,
    db: DB,
    use_ai: bool = Query(True, description="Use OpenAI to enhance the explanation"),
) -> dict:
    """
    Returns a full narrative explanation of why a transaction was flagged:
    what signals fired, what they mean, and what the owner should do.

    Example output:
    "This transaction looks suspicious because it happened at 2:14 AM,
    the amount (₦850,000) is 70% above your typical limit, and the same
    customer attempted payment 4 times in 20 minutes."
    """
    try:
        uid = UUID(fraud_log_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fraud log ID format")

    service = AIExplanationService(db)
    explanation = await service.explain_fraud_alert(uid, use_ai=use_ai)

    return success_response(data=explanation, message="Fraud explanation generated")


# ── 2. Explain revenue performance ────────────────────────────────────────────
@router.get(
    "/revenue",
    response_model=dict,
    summary="Get CFO-quality explanation for revenue performance",
)
async def explain_revenue(
    current_user: CurrentUser,
    db: DB,
    period: str = Query("last_30_days", enum=["last_7_days", "last_30_days", "this_month"]),
    use_ai: bool = Query(True),
) -> dict:
    """
    Explains revenue changes: what happened, why it happened (day patterns,
    customer gaps, seasonal context), and what to do about it.

    Example:
    "Your revenue dropped by 32% this week because Tuesday sales were
    unusually low and 3 customers who regularly pay on Fridays delayed
    their transactions."
    """
    service = AIExplanationService(db)
    explanation = await service.explain_revenue_change(
        current_user.id, period=period, use_ai=use_ai
    )
    return success_response(data=explanation, message="Revenue explanation generated")


# ── 3. Explain health score ───────────────────────────────────────────────────
@router.post(
    "/health-score",
    response_model=dict,
    summary="Explain a financial health score with improvement roadmap",
)
async def explain_health_score(
    current_user: CurrentUser,
    db: DB,
    score: int = Query(..., ge=0, le=100),
    grade: str = Query(...),
    label: str = Query(...),
    revenue_growth: int = Query(50, ge=0, le=100),
    fraud_safety: int = Query(50, ge=0, le=100),
    transaction_volume: int = Query(50, ge=0, le=100),
    previous_score: Optional[int] = Query(None),
    use_ai: bool = Query(True),
) -> dict:
    """
    Explains what the health score means and how to improve it.
    Identifies the weakest component and gives a targeted action plan.
    """
    service = AIExplanationService(db)
    explanation = await service.explain_health_score_change(
        user_id=current_user.id,
        current_score=score,
        grade=grade,
        label=label,
        breakdown={
            "revenue_growth": revenue_growth,
            "fraud_safety": fraud_safety,
            "transaction_volume": transaction_volume,
        },
        previous_score=previous_score,
        use_ai=use_ai,
    )
    return success_response(data=explanation, message="Health score explanation generated")


# ── 4. Explain a forecast ─────────────────────────────────────────────────────
@router.get(
    "/forecast/{forecast_id}",
    response_model=dict,
    summary="Explain a cash flow forecast result",
)
async def explain_forecast(
    forecast_id: str,
    current_user: CurrentUser,
    db: DB,
    use_ai: bool = Query(True),
) -> dict:
    """
    Explains the forecast: what it predicts, how confident we are,
    what risks could derail it, and what the owner should do to protect
    their projected income.
    """
    try:
        fid = UUID(forecast_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid forecast ID format")

    service = AIExplanationService(db)
    explanation = await service.explain_forecast_result(fid, use_ai=use_ai)
    return success_response(data=explanation, message="Forecast explanation generated")


# ── 5. Explain customer patterns ─────────────────────────────────────────────
@router.get(
    "/customers",
    response_model=dict,
    summary="Explain customer behaviour patterns",
)
async def explain_customers(
    current_user: CurrentUser,
    db: DB,
    period_days: int = Query(30, ge=7, le=90),
    use_ai: bool = Query(True),
) -> dict:
    """
    Explains what's happening with your customer base: retention rate,
    churn, new acquisition, concentration risk, and purchase frequency.
    """
    service = AIExplanationService(db)
    explanation = await service.explain_customer_patterns(
        current_user.id, period_days=period_days, use_ai=use_ai
    )
    return success_response(data=explanation, message="Customer behaviour explanation generated")


# ── 6. Ask your AI CFO anything ───────────────────────────────────────────────
class FinancialQuestionRequest(BaseModel):
    question: str
    language: str = "english"   # "english" | "pidgin"


@router.post(
    "/ask",
    response_model=dict,
    summary="Ask your AI CFO any financial question",
)
async def ask_cfo(
    payload: FinancialQuestionRequest,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """
    Natural language financial Q&A powered by GPT with your business context.

    Examples:
    - "Why did my revenue drop last week?"
    - "Which payment channel should I focus on?"
    - "How do I reduce my fraud rate?"
    - "Wetin dey cause my revenue to fall?" (Pidgin)
    """
    service = AIExplanationService(db)
    result = await service.answer_financial_question(
        user_id=current_user.id,
        question=payload.question,
        language=payload.language,
    )
    return success_response(data=result, message="AI CFO response generated")
