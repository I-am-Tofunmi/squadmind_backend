"""
SquadMind – Core Configuration
Centralised settings powered by Pydantic BaseSettings.
Every value is read from environment variables / .env file.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import List, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ─────────────────────────────────────────────────────────────────
    APP_NAME: str = "SquadMind"
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── API ─────────────────────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = secrets.token_hex(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Database ────────────────────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "squadmind"
    POSTGRES_USER: str = "squadmind_user"
    POSTGRES_PASSWORD: str = "password"

    # These are loaded from .env
    DATABASE_URL: Optional[str] = None
    DATABASE_URL_SYNC: Optional[str] = None

    @model_validator(mode="after")
    def build_db_urls(self) -> "Settings":
        """
        Force Async SQLAlchemy driver for DATABASE_URL
        while keeping sync URL for Alembic and sync tasks.
        """

        # If DATABASE_URL exists and starts with postgresql://
        # automatically convert it to asyncpg
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql://"):
                self.DATABASE_URL = self.DATABASE_URL.replace(
                    "postgresql://",
                    "postgresql+asyncpg://",
                    1
                )

        # If DATABASE_URL is missing, build async URL from local defaults
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

        # If sync URL missing, build normal psycopg2 URL
        if not self.DATABASE_URL_SYNC:
            self.DATABASE_URL_SYNC = (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

        return self

    # ── Redis ───────────────────────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Celery ──────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Squad API ───────────────────────────────────────────────────────────
    SQUAD_BASE_URL: str = "https://sandbox-api-d.squadco.com"
    SQUAD_SECRET_KEY: str = ""
    SQUAD_PUBLIC_KEY: str = ""
    SQUAD_WEBHOOK_SECRET: str = ""

    # ── OpenAI ──────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ── Twilio ──────────────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = "whatsapp:+14155238886"
    TWILIO_SMS_NUMBER: str = ""

    # ── SendGrid ────────────────────────────────────────────────────────────
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "noreply@squadmind.ai"
    SENDGRID_FROM_NAME: str = "SquadMind AI"

    # ── CORS ────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "https://squadmind-khaki.vercel.app,http://localhost:5173"


    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # ── Rate Limiting ───────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60

    # ── Fraud Detection ─────────────────────────────────────────────────────
    FRAUD_LARGE_TRANSACTION_THRESHOLD: float = 500000.0
    FRAUD_VELOCITY_WINDOW_MINUTES: int = 60
    FRAUD_VELOCITY_MAX_COUNT: int = 10
    FRAUD_NIGHT_HOUR_START: int = 23
    FRAUD_NIGHT_HOUR_END: int = 5

    # ── Forecasting ─────────────────────────────────────────────────────────
    FORECAST_DAYS_AHEAD: int = 30
    FORECAST_LOOKBACK_DAYS: int = 90

    # ── Helpers ─────────────────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance"""
    return Settings()


settings = get_settings()