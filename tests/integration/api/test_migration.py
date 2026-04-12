"""Integration tests for the Foundation Alembic migration."""

import os
import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, inspect, text
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="module")
def migration_container():
    """Dedicated PostgreSQL container for migration tests (isolated from shared pg_engine)."""
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="module")
def migration_engine(migration_container):
    """Fresh engine on the isolated migration container (no tables pre-created)."""
    url = migration_container.get_connection_url()
    engine = create_engine(url)
    yield engine
    engine.dispose()


def _alembic_cfg(db_url: str) -> AlembicConfig:
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_migration_creates_users_table(migration_engine, migration_container):
    url = migration_container.get_connection_url()
    os.environ["APP_USERNAME"] = "testadmin"
    os.environ["APP_PASSWORD"] = "testpassword123"
    try:
        command.upgrade(_alembic_cfg(url), "head")
        inspector = inspect(migration_engine)
        assert "users" in inspector.get_table_names()
        assert "ui_settings" in inspector.get_table_names()
    finally:
        command.downgrade(_alembic_cfg(url), "-1")
        del os.environ["APP_USERNAME"]
        del os.environ["APP_PASSWORD"]


def test_migration_seeds_user_and_settings(migration_engine, migration_container):
    url = migration_container.get_connection_url()
    os.environ["APP_USERNAME"] = "testadmin"
    os.environ["APP_PASSWORD"] = "testpassword123"
    try:
        command.upgrade(_alembic_cfg(url), "head")
        with migration_engine.connect() as conn:
            user_row = conn.execute(text("SELECT id, username FROM users WHERE id=1")).fetchone()
            assert user_row is not None
            assert user_row.username == "testadmin"

            settings = conn.execute(
                text("SELECT key, value FROM ui_settings WHERE user_id=1 ORDER BY key")
            ).fetchall()
            settings_dict = {r.key: r.value for r in settings}
            assert settings_dict["theme"] == "dark"
            assert settings_dict["timezone"] == "America/New_York"
    finally:
        command.downgrade(_alembic_cfg(url), "-1")
        del os.environ["APP_USERNAME"]
        del os.environ["APP_PASSWORD"]


def test_migration_downgrade_drops_tables(migration_engine, migration_container):
    url = migration_container.get_connection_url()
    os.environ["APP_USERNAME"] = "testadmin"
    os.environ["APP_PASSWORD"] = "testpassword123"
    try:
        command.upgrade(_alembic_cfg(url), "head")
        command.downgrade(_alembic_cfg(url), "base")
        inspector = inspect(migration_engine)
        assert "users" not in inspector.get_table_names()
        assert "ui_settings" not in inspector.get_table_names()
    finally:
        del os.environ["APP_USERNAME"]
        del os.environ["APP_PASSWORD"]


def test_migration_raises_without_credentials(migration_container, migration_engine):
    url = migration_container.get_connection_url()
    # Start from a clean state by downgrading to base first
    command.downgrade(_alembic_cfg(url), "base")
    # Clear environment variables
    for key in ("APP_USERNAME", "APP_PASSWORD"):
        os.environ.pop(key, None)
    with pytest.raises(Exception, match="APP_USERNAME"):
        command.upgrade(_alembic_cfg(url), "head")
