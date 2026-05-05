"""
SquadMind – User Schemas
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    business_name: str
    email: EmailStr
    phone: Optional[str] = None
    industry: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    business_name: Optional[str] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    whatsapp_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    email_alerts_enabled: Optional[bool] = None
    alert_phone: Optional[str] = None


class UserResponse(UserBase):
    id: UUID
    is_active: bool
    is_verified: bool
    has_squad_credentials: bool
    squad_last_synced_at: Optional[datetime] = None
    whatsapp_enabled: bool
    sms_enabled: bool
    email_alerts_enabled: bool
    alert_phone: Optional[str] = None
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
