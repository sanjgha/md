"""Database connection pooling."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def get_engine(
    database_url: str,
    pool_size: int = 5,
    max_overflow: int = 15,
    echo: bool = False,
) -> Engine:
    """Create database engine with connection pooling."""
    engine = create_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        echo=echo,
        connect_args=(
            {"connect_timeout": 10, "application_name": "market_data"}
            if "postgresql" in database_url
            else {}
        ),
    )
    return engine


def init_db(engine: Engine) -> None:
    """Initialize database with schema."""
    from src.db.models import Base

    Base.metadata.create_all(engine)
