"""
SquadMind – TrustScore API
Exposes lender-ready SME creditworthiness scoring.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.api.deps import get_current_user
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
async def get_trust_score(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dynamic lender-facing TrustScore endpoint.
    """

    trust_score: TrustScoreResponse = await calculate_trust_score(
        db=db,
        user_id=current_user.id,
    )

    return {
        "success": True,
        "message": "TrustScore generated successfully",
        "data": trust_score.model_dump(),
        "error": None,
    }