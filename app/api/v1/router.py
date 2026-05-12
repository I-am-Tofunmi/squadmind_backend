"""
SquadMind – API v1 Router
Aggregates all sub-routers into the v1 prefix.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.transactions import router as transactions_router
from app.api.v1.fraud import router as fraud_router
from app.api.v1.forecasts import router as forecasts_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.trust_score import router as trust_score_router
from app.api.v1.virtual_account import router as virtual_accounts_router

api_router = APIRouter()

# Core Routes
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(transactions_router)
api_router.include_router(fraud_router)
api_router.include_router(forecasts_router)
api_router.include_router(alerts_router)
api_router.include_router(trust_score_router)

# Virtual Accounts
api_router.include_router(virtual_accounts_router)