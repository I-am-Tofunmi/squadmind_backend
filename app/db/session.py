"""
SquadMind – Database Session
Async SQLAlchemy engine, session factory, and FastAPI dependency.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)



# ── Engine ───────────────────────────────────────────────────────────────────
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,          # validates connections before use
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,           # recycle connections every hour
    echo=settings.DEBUG,         # log SQL in dev mode only
    future=True,
    connect_args={
        "statement_cache_size": 0
    }
)

# ── Session Factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,      # avoid lazy-load errors after commit
    autocommit=False,
    autoflush=False,
)

# ── FastAPI Dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async DB session for each request.
    Automatically rolls back on exception and always closes.

    Usage in route:
        async def my_route(db: AsyncSession = Depends(get_db)):
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Context Manager (for scripts / workers) ───────────────────────────────────
@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for use outside of FastAPI request scope.
    Use in Celery tasks, CLI scripts, etc.

    Usage:
        async with get_db_context() as db:
            result = await db.execute(...)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Health Check ──────────────────────────────────────────────────────────────
async def check_db_connection() -> bool:
    """Ping the database. Used in /health endpoint."""
    try:
        from sqlalchemy import text

        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))

        return True

    except Exception as e:
        log.error("database_health_check_failed", error=str(e))
        return False