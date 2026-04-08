"""Alembic environment configuration wired to project models and get_config()."""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add project root to sys.path so src.* imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.config import get_config  # noqa: E402
from src.db.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Return database URL: prefer explicit sqlalchemy.url from config, else app config."""
    # When tests (or CLI) set sqlalchemy.url explicitly via AlembicConfig.set_main_option,
    # use that directly so we don't require DATABASE_URL / MARKETDATA_API_TOKEN env vars.
    explicit_url = config.get_main_option("sqlalchemy.url")
    if explicit_url:
        return explicit_url
    return get_config().DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection required)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (requires DB connection)."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
