"""
SquadMind – API Dependencies
Reusable FastAPI dependencies: current user extraction, DB, Redis, rate limiting.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import decode_token
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User

log = get_logger(__name__)

# ── HTTP Bearer extractor (no auto_error so we can return custom 401) ─────────
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate the Bearer token and return the authenticated User.
    Raises HTTP 401 on any auth failure.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    try:
        payload = decode_token(credentials.credentials)
        token_type: str = payload.get("type", "")
        if token_type != "access":
            raise credentials_exception
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError as e:
        log.warning("jwt_decode_failed", error=str(e))
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact support.",
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Alias — use this when you just need an authenticated, active user."""
    return current_user


async def get_squad_enabled_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Only proceeds if the user has Squad API credentials attached.
    Use on routes that proxy Squad data.
    """
    if not current_user.has_squad_credentials:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Squad API credentials not configured. Please add your Squad keys in Settings.",
        )
    return current_user


# ── Type aliases for cleaner route signatures ─────────────────────────────────
CurrentUser = Annotated[User, Depends(get_current_user)]
SquadUser = Annotated[User, Depends(get_squad_enabled_user)]
DB = Annotated[AsyncSession, Depends(get_db)]
Redis = Annotated[aioredis.Redis, Depends(get_redis)]
