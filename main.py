"""
SquadMind – FastAPI Application Entry Point
Production-ready setup: lifespan, CORS, error handlers, health check, docs.
"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.redis import check_redis_connection
from app.db.session import check_db_connection

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    log.info(
        "squadmind_starting",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
    )

    # ── Create tables on startup ───────────────────────────────────────────────
    try:
        sync_url = os.environ.get("DATABASE_URL_SYNC")
        if sync_url:
            from sqlalchemy import create_engine
            from app.db.base import Base
            from app.models.user import User
            from app.models.transaction import Transaction
            from app.models.alert import Alert
            from app.models.fraud_log import FraudLog
            from app.models.forecast import Forecast
            from app.models.virtual_account import VirtualAccount
            _engine = create_engine(sync_url)
            Base.metadata.create_all(_engine)
            _engine.dispose()
            log.info("database_tables_created")
    except Exception as e:
        log.error("database_table_creation_failed", error=str(e))

    # ── Verify connections ─────────────────────────────────────────────────────
    db_ok = await check_db_connection()
    if not db_ok:
        log.error("database_connection_failed_at_startup")

    redis_ok = await check_redis_connection()
    if not redis_ok:
        log.warning("redis_connection_failed_at_startup")

    log.info(
        "squadmind_ready",
        db_healthy=db_ok,
        redis_healthy=redis_ok,
    )

    yield

    log.info("squadmind_shutting_down")
    from app.db.session import engine
    await engine.dispose()
    log.info("squadmind_shutdown_complete")


def create_application() -> FastAPI:
    app = FastAPI(
        title="SquadMind API",
        description=(
            "AI-powered CFO platform for Nigerian SMEs. "
            "Revenue intelligence, fraud detection, cash flow forecasting, and smart alerts."
        ),
        version=settings.APP_VERSION,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time"],
    )

    @app.middleware("http")
    async def add_timing_header(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        log.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "An unexpected error occurred. Our team has been notified.",
                "data": None,
                "error": "internal_server_error",
            },
        )

    from fastapi import HTTPException

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.detail,
                "data": None,
                "error": exc.detail,
            },
            headers=getattr(exc, "headers", None),
        )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["System"], include_in_schema=False)
    async def health_check():
        db_ok = await check_db_connection()
        redis_ok = await check_redis_connection()
        return {
            "status": "ok" if (db_ok and redis_ok) else "degraded",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "services": {
                "database": "healthy" if db_ok else "unhealthy",
                "redis": "healthy" if redis_ok else "unhealthy",
            },
        }

    @app.get("/", tags=["System"], include_in_schema=False)
    async def root():
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "tagline": "AI-Powered CFO for Nigerian SMEs 🇳🇬",
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_application()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
    )
