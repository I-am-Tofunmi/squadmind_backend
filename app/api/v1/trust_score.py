"""
SquadMind – TrustScore API
Exposes lender-ready SME creditworthiness scoring.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.trust_score import TrustScoreResponse
from app.services.trust_score import calculate_trust_score


router = APIRouter(
    prefix="/trust-score",
    tags=["Trust Score"],
)


@router.get(
    "",
    response_model=dict,
    summary="Get SME TrustScore",
    description=(
        "Returns business creditworthiness score using "
        "behavioral transaction intelligence instead of traditional credit history."
    ),
)
async def get_trust_score():
    """
    Core lender-facing endpoint.
    """

    trust_score: TrustScoreResponse = calculate_trust_score()

    return {
        "success": True,
        "message": "TrustScore generated successfully",
        "data": trust_score.model_dump(),
        "error": None,
    }