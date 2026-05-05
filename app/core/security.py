"""
SquadMind – Security Utilities
JWT token creation/verification, password hashing, and auth guards.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ── Password Hashing ─────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Return bcrypt hash of the plain password."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── Token Helpers ────────────────────────────────────────────────────────────
def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(
    subject: Union[str, UUID],
    extra_claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject:      User ID (str or UUID) stored in the 'sub' claim.
        extra_claims: Optional dict merged into the payload (e.g. role, email).
        expires_delta: Override default expiry window.

    Returns:
        Signed JWT string.
    """
    expire = _utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "iat": _utcnow(),
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: Union[str, UUID]) -> str:
    """Create a long-lived refresh token."""
    expire = _utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(subject),
        "iat": _utcnow(),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT token.

    Raises:
        JWTError: if token is invalid, expired, or tampered with.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def extract_user_id(token: str) -> str:
    """
    Extract the user ID from a verified JWT token.

    Raises:
        JWTError: on any decode failure.
    """
    payload = decode_token(token)
    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise JWTError("Token missing 'sub' claim")
    return user_id


# ── Token Pair Factory ───────────────────────────────────────────────────────
def create_token_pair(
    user_id: Union[str, UUID],
    extra_claims: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Generate both access and refresh tokens in one shot.
    Frontend stores both; access token goes in Authorization header,
    refresh token used to renew without re-login.
    """
    return {
        "access_token": create_access_token(user_id, extra_claims=extra_claims),
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
    }
