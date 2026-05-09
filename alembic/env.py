"""
Alembic Environment Configuration for SquadMind.
Supports both offline (SQL generation) and online (live DB) migration modes.
Uses the synchronous DATABASE_URL_SYNC for migrations.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── Load app config ────────────────────────────────────────────────────────────
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings

# ── Register all models so Alembic sees them ──────────────────────────────────
from app.db.base import Base  # noqa: F401 — this import registers all models
from app.models.user import User
from app.models.transaction import Transaction
from app.models.alert import Alert
from app.models.fraud_log import FraudLog
from app.models.forecast import Forecast

# Alembic config object
config = context.config

# Override the SQLAlchemy URL from our app settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)

# Set up Python logging from alembic.ini if present
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Generates SQL scripts without a live database connection.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    Connects to the live database and applies changes directly.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
