"""Tests for database connection module."""

from sqlalchemy.pool import Pool
from src.db.connection import get_engine


def test_get_engine_creates_pool(pg_engine):
    """Verify pg_engine fixture returns a pooled engine."""
    assert pg_engine is not None
    assert isinstance(pg_engine.pool, Pool)


def test_engine_uses_pool_pre_ping(postgres_container):
    """Verify engine is created with pool_pre_ping enabled."""
    engine = get_engine(
        database_url=postgres_container.get_connection_url(),
        pool_size=5,
        max_overflow=15,
    )
    assert engine.pool.size() == 5
