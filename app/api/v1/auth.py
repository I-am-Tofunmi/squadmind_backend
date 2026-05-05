"""
SquadMind – Auth Router  /api/v1/auth
Endpoints: register · login · refresh · me · update profile · squad credentials
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DB
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import (
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    RefreshRequest,
    RegisterRequest,
    SquadCredentialsRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse, UserUpdate
from app.utils.responses import success_response, error_response

log = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new SME business account",
)
async def register(payload: RegisterRequest, db: DB) -> dict:
    """
    Create a new SquadMind account tied to a Nigerian SME.
    Returns token pair so the user is immediately logged in.
    """
    # Check duplicate email
    existing = await db.execute(select(User).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        business_name=payload.business_name,
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        phone=payload.phone,
        industry=payload.industry,
    )
    db.add(user)

    try:
        await db.flush()   # get the UUID before commit
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration failed due to a conflict. Please try again.",
        )

    tokens = create_token_pair(
        user.id,
        extra_claims={"email": user.email, "business": user.business_name},
    )

    log.info("user_registered", user_id=str(user.id), email=user.email)

    return success_response(
        data={
            **tokens,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": str(user.id),
                "business_name": user.business_name,
                "email": user.email,
                "has_squad_credentials": False,
            },
        },
        message="Account created successfully. Welcome to SquadMind!",
    )


@router.post(
    "/login",
    response_model=dict,
    summary="Login and receive JWT token pair",
)
async def login(payload: LoginRequest, db: DB) -> dict:
    """Authenticate with email + password. Returns access + refresh tokens."""
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )

    # Update last login
    user.last_login_at = datetime.now(tz=timezone.utc)

    tokens = create_token_pair(
        user.id,
        extra_claims={"email": user.email, "business": user.business_name},
    )

    log.info("user_logged_in", user_id=str(user.id), email=user.email)

    return success_response(
        data={
            **tokens,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": str(user.id),
                "business_name": user.business_name,
                "email": user.email,
                "has_squad_credentials": user.has_squad_credentials,
                "squad_last_synced_at": (
                    user.squad_last_synced_at.isoformat()
                    if user.squad_last_synced_at
                    else None
                ),
            },
        },
        message="Login successful",
    )


@router.post(
    "/refresh",
    response_model=dict,
    summary="Exchange refresh token for a new access token",
)
async def refresh_token(payload: RefreshRequest, db: DB) -> dict:
    """Use refresh token to get a new access token without re-login."""
    from jose import JWTError

    try:
        token_data = decode_token(payload.refresh_token)
        if token_data.get("type") != "refresh":
            raise HTTPException(status_code=400, detail="Invalid token type")
        user_id = token_data.get("sub")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    from uuid import UUID
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive.")

    from app.core.security import create_access_token
    new_access = create_access_token(
        user.id,
        extra_claims={"email": user.email, "business": user.business_name},
    )

    return success_response(
        data={
            "access_token": new_access,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        },
        message="Token refreshed",
    )


@router.get(
    "/me",
    response_model=dict,
    summary="Get the authenticated user's profile",
)
async def get_me(current_user: CurrentUser) -> dict:
    """Return the current user's profile. Validates the token is still good."""
    return success_response(
        data=UserResponse.model_validate(current_user).model_dump(mode="json"),
        message="Profile retrieved",
    )


@router.patch(
    "/me",
    response_model=dict,
    summary="Update profile settings",
)
async def update_profile(
    payload: UserUpdate,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """Update mutable profile fields."""
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)

    log.info("user_profile_updated", user_id=str(current_user.id))
    return success_response(
        data=UserResponse.model_validate(current_user).model_dump(mode="json"),
        message="Profile updated",
    )


@router.post(
    "/squad-credentials",
    response_model=dict,
    summary="Attach Squad API keys to your account",
)
async def save_squad_credentials(
    payload: SquadCredentialsRequest,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """
    Store encrypted Squad API keys.
    After this, transaction syncing becomes available.
    """
    # In production you'd encrypt these at rest; for MVP store as-is
    current_user.squad_secret_key = payload.squad_secret_key
    current_user.squad_public_key = payload.squad_public_key
    if payload.squad_merchant_id:
        current_user.squad_merchant_id = payload.squad_merchant_id

    log.info("squad_credentials_saved", user_id=str(current_user.id))
    return success_response(
        data={"has_squad_credentials": True},
        message="Squad API credentials saved. You can now sync your transactions.",
    )


@router.post(
    "/change-password",
    response_model=dict,
    summary="Change account password",
)
async def change_password(
    payload: PasswordChangeRequest,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    current_user.hashed_password = hash_password(payload.new_password)
    log.info("password_changed", user_id=str(current_user.id))
    return success_response(data={}, message="Password changed successfully.")
