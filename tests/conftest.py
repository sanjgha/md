"""Shared pytest fixtures using testcontainers PostgreSQL."""

import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL container for the test session."""
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def pg_engine(postgres_container):
    """Create a SQLAlchemy engine connected to the test PostgreSQL container."""
    from src.db.models import Base

    engine = create_engine(postgres_container.get_connection_url())
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(pg_engine):
    """Provide a transactional database session that rolls back after each test."""
    SessionLocal = sessionmaker(bind=pg_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()
