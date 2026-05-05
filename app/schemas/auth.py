"""
SquadMind – Auth Schemas
Pydantic models for registration, login, token responses.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=255, examples=["Lagos Traders Ltd"])
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    phone: Optional[str] = Field(None, pattern=r"^\+?[\d\s\-]{7,20}$")
    industry: Optional[str] = Field(None, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int   # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class SquadCredentialsRequest(BaseModel):
    """Attach Squad API keys to the authenticated account."""
    squad_secret_key: str = Field(..., min_length=10)
    squad_public_key: str = Field(..., min_length=10)
    squad_merchant_id: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v
