"""
SquadMind – API v1 Router
Aggregates all sub-routers into the v1 prefix.
"""

from fastapi import APIRouter

from app.api.v1 import auth, dashboard, transactions, fraud, forecasts, alerts

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(transactions.router)
api_router.include_router(fraud.router)
api_router.include_router(forecasts.router)
api_router.include_router(alerts.router)
