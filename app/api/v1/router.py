"""
SquadMind – API v1 Router
Aggregates all sub-routers into the v1 prefix.
"""

from fastapi import APIRouter

from app.api.v1 import auth
from app.api.v1 import dashboard
from app.api.v1 import transactions
from app.api.v1 import fraud
from app.api.v1 import forecasts
from app.api.v1 import alerts

import app.api.v1.trust_score as trust_score

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(transactions.router)
api_router.include_router(fraud.router)
api_router.include_router(forecasts.router)
api_router.include_router(alerts.router)
api_router.include_router(trust_score.router)