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
    """Provide a database session that truncates all tables after each test."""
    from sqlalchemy import text
    from src.db.models import Base

    SessionLocal = sessionmaker(bind=pg_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()
    # Truncate all tables to ensure full isolation between tests that commit
    with pg_engine.connect() as conn:
        table_names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
        conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
        conn.commit()
