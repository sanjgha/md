# Market Data Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a hybrid Python/PostgreSQL market data infrastructure supporting 500-stock EOD scanning, realtime monitoring, and backtesting with pluggable data providers.

**Architecture:** Modular Python application with PostgreSQL backend, pluggable DataProvider adapters, indicator caching framework during EOD runs, and flexible output abstraction (CLI/logs now, dashboard later). Clean separation enables scanner isolation, reduces code duplication, and supports future dashboard integration without rearchitecture.

**Tech Stack:** Python 3.11+, PostgreSQL 14+, SQLAlchemy ORM, Alembic, APScheduler, NumPy/Pandas for indicators, requests for HTTP, pytest + testcontainers for testing.

---

## File Structure Overview

```
md/
├── src/
│   ├── __init__.py
│   ├── config.py                      # Config class + get_config() factory (lazy)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py                  # All ORM models incl. EconomicIndicator
│   │   ├── connection.py              # Connection pooling
│   │   └── migrations/               # Alembic migrations
│   ├── data_provider/
│   │   ├── __init__.py
│   │   ├── base.py                    # Abstract DataProvider + dataclasses
│   │   ├── marketdata_app.py          # MarketData.app with validation + timeouts
│   │   ├── validation.py              # validate_symbol, validate_resolution
│   │   └── exceptions.py             # Provider-specific errors
│   ├── data_fetcher/
│   │   ├── __init__.py
│   │   ├── fetcher.py                 # DataFetcher: sync_daily, sync_intraday, sync_news, sync_earnings
│   │   └── scheduler.py              # APScheduler 4:15 PM ET cron
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── indicators/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # Abstract Indicator
│   │   │   ├── cache.py               # IndicatorCache
│   │   │   ├── moving_averages.py     # SMA, EMA (fixed warmup), WMA
│   │   │   ├── momentum.py            # RSI (fixed seed), MACD
│   │   │   ├── volatility.py          # BollingerBands, ATR
│   │   │   ├── support_resistance.py  # SupportResistance
│   │   │   └── patterns/
│   │   │       ├── __init__.py
│   │   │       ├── breakouts.py       # BreakoutDetector
│   │   │       └── candlestick.py     # CandlestickPatterns
│   │   ├── base.py                    # Scanner abstract + ScanResult (single def)
│   │   ├── scanners/
│   │   │   ├── __init__.py
│   │   │   ├── price_action.py
│   │   │   ├── momentum_scan.py
│   │   │   └── volume_scan.py         # VolumeScanner
│   │   ├── executor.py               # ORM→dataclass conversion, batch commits, joinedload
│   │   ├── registry.py
│   │   └── context.py
│   ├── realtime_monitor/
│   │   ├── __init__.py
│   │   ├── monitor.py                # Fixed db.query(Stock), batch commits
│   │   ├── alert_engine.py
│   │   └── rules.py
│   ├── output/
│   │   ├── __init__.py
│   │   ├── base.py                   # OutputHandler + Alert; imports ScanResult from scanner.base
│   │   ├── cli.py
│   │   ├── logger.py
│   │   └── composite.py              # Fixed exception logging
│   └── main.py                       # Lazy DB init, seed-universe + schedule commands
├── tests/
│   ├── conftest.py                   # testcontainers PostgreSQL fixtures
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_db_connection.py
│   │   ├── test_db_models.py
│   │   ├── test_data_provider_base.py
│   │   ├── test_data_provider_validation.py
│   │   ├── test_marketdata_provider.py
│   │   ├── test_indicator_cache.py
│   │   ├── test_indicators.py         # SMA, EMA, RSI, BB, ATR, patterns
│   │   ├── test_scanners.py
│   │   ├── test_scanner_implementations.py # price_action, momentum, volume
│   │   ├── test_output_handlers.py
│   │   └── test_alert_rules.py
│   ├── integration/
│   │   ├── test_fetcher_db.py         # sync_daily, sync_intraday, sync_news bulk upsert
│   │   └── test_end_to_end.py         # Full pipeline with real PostgreSQL
│   └── fixtures/
│       └── mock_data.py
├── pyproject.toml                    # + testcontainers[postgres], alembic, pytz
├── Makefile
└── README.md
```

---

## Phase 1: Foundation & Project Setup

### Task 1: Initialize Python project (pyproject.toml, Makefile, .env.example)

**Files:**
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `src/__init__.py`
- Create: `.env.example`

- [x] **Step 1: Write pyproject.toml with all dependencies**

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "market-data"
version = "0.1.0"
description = "Hybrid market data infrastructure for 500-stock universe"
requires-python = ">=3.11"
dependencies = [
    "sqlalchemy>=2.0.0",
    "psycopg2-binary>=2.9.9",
    "alembic>=1.13.0",
    "requests>=2.31.0",
    "numpy>=1.24.0",
    "pandas>=2.1.0",
    "apscheduler>=3.10.0",
    "python-dotenv>=1.0.0",
    "click>=8.1.0",
    "pytz>=2024.1",
    "python-dateutil>=2.9.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.5.0",
    "testcontainers[postgres]>=3.7.0",
]

[tool.setuptools]
packages = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --cov=src --cov-report=term-missing"

[tool.black]
line-length = 100

[tool.ruff]
line-length = 100
```

- [x] **Step 2: Create Makefile for common tasks**

```makefile
.PHONY: install dev-install test lint format clean

install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"

test:
	pytest tests/

test-cov:
	pytest tests/ --cov=src --cov-report=html

lint:
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

format:
	black src/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache build/ dist/ *.egg-info htmlcov/
```

- [x] **Step 3: Create .env.example**

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/market_data

# MarketData.app API
MARKETDATA_API_TOKEN=your_token_here

# Application
LOG_LEVEL=INFO
LOG_FILE=logs/market_data.log
```

- [x] **Step 4: Create src/__init__.py**

```python
"""Market Data Infrastructure."""

__version__ = "0.1.0"
```

- [x] **Step 5: Commit**

```bash
git add pyproject.toml Makefile .env.example src/__init__.py
git commit -m "feat: initialize Python project with dependencies and build config"
```

---

### Task 2: Config module with lazy get_config() factory

**Files:**
- Create: `src/config.py`
- Create: `tests/unit/test_config.py`

- [x] **Step 1: Write failing tests for config loading**

```python
# tests/unit/test_config.py
import os
import pytest
from unittest.mock import patch

def test_config_loads_from_env():
    with patch.dict(os.environ, {
        "DATABASE_URL": "postgresql://test:test@localhost/testdb",
        "MARKETDATA_API_TOKEN": "test_token_123",
    }):
        # Import fresh — lru_cache must be cleared between tests
        from importlib import import_module, reload
        import src.config as cfg_module
        reload(cfg_module)
        cfg_module.get_config.cache_clear()
        config = cfg_module.get_config()
        assert config.DATABASE_URL == "postgresql://test:test@localhost/testdb"
        assert config.MARKETDATA_API_TOKEN == "test_token_123"

def test_config_raises_on_missing_required():
    env = {k: v for k, v in os.environ.items()
           if k not in ("DATABASE_URL", "MARKETDATA_API_TOKEN")}
    with patch.dict(os.environ, env, clear=True):
        from importlib import reload
        import src.config as cfg_module
        reload(cfg_module)
        cfg_module.get_config.cache_clear()
        with pytest.raises(ValueError):
            cfg_module.get_config()

def test_config_defaults():
    with patch.dict(os.environ, {
        "DATABASE_URL": "postgresql://test:test@localhost/testdb",
        "MARKETDATA_API_TOKEN": "test_token_123",
    }):
        from importlib import reload
        import src.config as cfg_module
        reload(cfg_module)
        cfg_module.get_config.cache_clear()
        config = cfg_module.get_config()
        assert config.LOG_LEVEL == "INFO"
        assert config.STOCK_UNIVERSE_SIZE == 500
        assert config.MAX_RETRIES == 5
```

- [x] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_config.py::test_config_loads_from_env -v
```

Expected output: `FAILED — get_config not defined`

- [x] **Step 3: Implement Config class with get_config() factory**

```python
# src/config.py
import os
from pathlib import Path
from dotenv import load_dotenv
from functools import lru_cache


class Config:
    def __init__(self):
        self.DATABASE_URL = os.getenv("DATABASE_URL")
        self.MARKETDATA_API_TOKEN = os.getenv("MARKETDATA_API_TOKEN")
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FILE = os.getenv("LOG_FILE", "logs/market_data.log")

        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is required")
        if not self.MARKETDATA_API_TOKEN:
            raise ValueError("MARKETDATA_API_TOKEN environment variable is required")

        self.STOCK_UNIVERSE_SIZE = 500
        self.MAX_RETRIES = 5
        self.RETRY_BACKOFF_BASE = 1
        self.CONNECTION_POOL_MIN = 5
        self.CONNECTION_POOL_MAX = 20
        self.DAILY_CANDLE_RETENTION_YEARS = 1
        self.INTRADAY_RETENTION_DAYS = 7
        self.QUOTE_RETENTION_DAYS = 7
        self.API_RATE_LIMIT_DELAY = 0.1


@lru_cache(maxsize=1)
def get_config() -> Config:
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    return Config()
```

- [x] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_config.py -v
```

Expected output: `3 passed`

- [x] **Step 5: Commit**

```bash
git add src/config.py tests/unit/test_config.py
git commit -m "feat: add Config class with lazy get_config() factory"
```

---

## Phase 2: Database & ORM

### Task 3: DB connection pooling + testcontainers conftest

**Files:**
- Create: `src/db/__init__.py`
- Create: `src/db/connection.py`
- Create: `tests/conftest.py`
- Create: `tests/unit/test_db_connection.py`

- [x] **Step 1: Write failing test for connection pool**

```python
# tests/unit/test_db_connection.py
import pytest
from sqlalchemy.pool import Pool
from src.db.connection import get_engine


def test_get_engine_creates_pool(pg_engine):
    assert pg_engine is not None
    assert isinstance(pg_engine.pool, Pool)


def test_engine_uses_pool_pre_ping(postgres_container):
    from src.db.connection import get_engine
    engine = get_engine(
        database_url=postgres_container.get_connection_url(),
        pool_size=5,
        max_overflow=15,
    )
    assert engine.pool.size() == 5
```

- [x] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_db_connection.py::test_get_engine_creates_pool -v
```

Expected output: `FAILED — get_engine not defined`

- [x] **Step 3: Implement connection.py**

```python
# src/db/connection.py
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
```

- [x] **Step 4: Create db/__init__.py**

```python
# src/db/__init__.py
from src.db.connection import get_engine, init_db

__all__ = ["get_engine", "init_db"]
```

- [x] **Step 5: Create tests/conftest.py with testcontainers PostgreSQL fixtures**

```python
# tests/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.db.models import Base


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def pg_engine(postgres_container):
    engine = create_engine(postgres_container.get_connection_url())
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(pg_engine):
    SessionLocal = sessionmaker(bind=pg_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()
```

- [x] **Step 6: Run tests**

```bash
pytest tests/unit/test_db_connection.py -v
```

Expected output: `2 passed`

- [x] **Step 7: Commit**

```bash
git add src/db/connection.py src/db/__init__.py tests/conftest.py tests/unit/test_db_connection.py
git commit -m "feat: add database connection pooling and testcontainers PostgreSQL fixtures"
```

---

### Task 4: SQLAlchemy ORM models (all tables, fixed BRIN, fixed JSONB default, EconomicIndicator)

**Files:**
- Create: `src/db/models.py`
- Create: `tests/unit/test_db_models.py`

- [x] **Step 1: Write failing tests for ORM models**

```python
# tests/unit/test_db_models.py
import pytest
from datetime import datetime
from src.db.models import Base, Stock, DailyCandle, EconomicIndicator


def test_stock_model_creation(db_session):
    stock = Stock(symbol="AAPL", name="Apple Inc.", sector="Technology")
    db_session.add(stock)
    db_session.commit()

    retrieved = db_session.query(Stock).filter_by(symbol="AAPL").first()
    assert retrieved is not None
    assert retrieved.name == "Apple Inc."
    assert retrieved.sector == "Technology"


def test_daily_candle_relationship(db_session):
    stock = Stock(symbol="MSFT", name="Microsoft", sector="Technology")
    db_session.add(stock)
    db_session.flush()

    candle = DailyCandle(
        stock_id=stock.id,
        timestamp=datetime(2024, 1, 2),
        open=150.0,
        high=152.0,
        low=149.0,
        close=151.0,
        volume=1000000,
    )
    db_session.add(candle)
    db_session.commit()

    retrieved = db_session.query(Stock).filter_by(symbol="MSFT").first()
    assert len(retrieved.daily_candles) == 1
    assert float(retrieved.daily_candles[0].close) == 151.0


def test_economic_indicator_model(db_session):
    ei = EconomicIndicator(
        indicator_name="CPI",
        release_date=datetime(2024, 1, 15),
        value=3.4,
        unit="percent",
    )
    db_session.add(ei)
    db_session.commit()

    retrieved = db_session.query(EconomicIndicator).filter_by(indicator_name="CPI").first()
    assert retrieved is not None
    assert float(retrieved.value) == 3.4


def test_scanner_result_jsonb_default(db_session):
    from src.db.models import ScannerResult
    stock = Stock(symbol="TSLA", name="Tesla")
    db_session.add(stock)
    db_session.flush()

    r1 = ScannerResult(stock_id=stock.id, scanner_name="test", matched_at=datetime.utcnow())
    r2 = ScannerResult(stock_id=stock.id, scanner_name="test2", matched_at=datetime.utcnow())
    db_session.add_all([r1, r2])
    db_session.commit()

    # Verify the two rows have independent metadata dicts (not the same object)
    r1.result_metadata["key"] = "val"
    assert "key" not in (r2.result_metadata or {})
```

- [x] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_db_models.py::test_stock_model_creation -v
```

Expected output: `FAILED — Stock not defined`

- [x] **Step 3: Implement models.py with all core tables**

```python
# src/db/models.py
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, BigInteger, DateTime,
    Text, ForeignKey, NUMERIC, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Stock(Base):
    """Stock universe reference table."""
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255))
    sector = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    daily_candles = relationship("DailyCandle", back_populates="stock", cascade="all, delete-orphan")
    intraday_candles = relationship("IntradayCandle", back_populates="stock", cascade="all, delete-orphan")
    realtime_quotes = relationship("RealtimeQuote", back_populates="stock", cascade="all, delete-orphan")
    earnings = relationship("EarningsCalendar", back_populates="stock", cascade="all, delete-orphan")
    news = relationship("StockNews", back_populates="stock", cascade="all, delete-orphan")
    options = relationship("OptionsQuote", back_populates="stock", cascade="all, delete-orphan")
    scanner_results = relationship("ScannerResult", back_populates="stock", cascade="all, delete-orphan")


class DailyCandle(Base):
    """Daily OHLCV data (1-year retention)."""
    __tablename__ = "daily_candles"

    id = Column(BigInteger, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open = Column(NUMERIC(10, 2), nullable=False)
    high = Column(NUMERIC(10, 2), nullable=False)
    low = Column(NUMERIC(10, 2), nullable=False)
    close = Column(NUMERIC(10, 2), nullable=False)
    volume = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # B-tree index — BRIN is unsuitable for concurrent multi-stock inserts
    __table_args__ = (
        UniqueConstraint("stock_id", "timestamp", name="uq_daily_candles_stock_ts"),
        Index("ix_daily_candles_stock_ts", "stock_id", "timestamp"),
    )

    stock = relationship("Stock", back_populates="daily_candles")


class IntradayCandle(Base):
    """Intraday bars (5m, 15m, 1h; 7-day retention)."""
    __tablename__ = "intraday_candles"

    id = Column(BigInteger, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    resolution = Column(String(10), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open = Column(NUMERIC(10, 2), nullable=False)
    high = Column(NUMERIC(10, 2), nullable=False)
    low = Column(NUMERIC(10, 2), nullable=False)
    close = Column(NUMERIC(10, 2), nullable=False)
    volume = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("stock_id", "resolution", "timestamp", name="uq_intraday_candles_stock_res_ts"),
        Index("ix_intraday_candles_stock_ts", "stock_id", "timestamp"),
    )

    stock = relationship("Stock", back_populates="intraday_candles")


class RealtimeQuote(Base):
    """Realtime quotes with intraday summary (7-day retention)."""
    __tablename__ = "realtime_quotes"

    id = Column(BigInteger, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    bid = Column(NUMERIC(10, 2))
    ask = Column(NUMERIC(10, 2))
    bid_size = Column(BigInteger)
    ask_size = Column(BigInteger)
    last = Column(NUMERIC(10, 2))
    open = Column(NUMERIC(10, 2))
    high = Column(NUMERIC(10, 2))
    low = Column(NUMERIC(10, 2))
    close = Column(NUMERIC(10, 2))
    volume = Column(BigInteger)
    change = Column(NUMERIC(10, 4))
    change_pct = Column(NUMERIC(10, 4))
    week_52_high = Column(NUMERIC(10, 2))
    week_52_low = Column(NUMERIC(10, 2))
    status = Column(String(50))
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_realtime_quotes_stock_ts", "stock_id", "timestamp"),
    )

    stock = relationship("Stock", back_populates="realtime_quotes")


class EarningsCalendar(Base):
    """Earnings calendar (no retention limit)."""
    __tablename__ = "earnings_calendar"

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    fiscal_year = Column(Integer)
    fiscal_quarter = Column(Integer)
    earnings_date = Column(DateTime, nullable=False)
    report_date = Column(DateTime)
    report_time = Column(String(50))
    currency = Column(String(10))
    reported_eps = Column(NUMERIC(10, 4))
    estimated_eps = Column(NUMERIC(10, 4))
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("stock_id", "earnings_date", name="uq_earnings_stock_date"),
        Index("ix_earnings_date", "earnings_date"),
    )

    stock = relationship("Stock", back_populates="earnings")


class StockNews(Base):
    """Stock news articles."""
    __tablename__ = "stock_news"

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    headline = Column(Text, nullable=False)
    content = Column(Text)
    source = Column(String(255))
    publication_date = Column(DateTime, nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_stock_news_stock_pubdate", "stock_id", "publication_date"),
        Index("ix_stock_news_pubdate", "publication_date"),
    )

    stock = relationship("Stock", back_populates="news")


class OptionsQuote(Base):
    """Options quotes with Greeks (Phase 2; 7-day retention)."""
    __tablename__ = "options_quotes"

    id = Column(BigInteger, primary_key=True)
    option_symbol = Column(String(50), nullable=False)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    bid = Column(NUMERIC(10, 2))
    ask = Column(NUMERIC(10, 2))
    bid_size = Column(BigInteger)
    ask_size = Column(BigInteger)
    last = Column(NUMERIC(10, 2))
    volume = Column(BigInteger)
    open_interest = Column(BigInteger)
    delta = Column(NUMERIC(10, 4))
    gamma = Column(NUMERIC(10, 4))
    theta = Column(NUMERIC(10, 4))
    vega = Column(NUMERIC(10, 4))
    iv = Column(NUMERIC(10, 4))
    underlying_price = Column(NUMERIC(10, 2))
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("option_symbol", "timestamp", name="uq_options_symbol_ts"),
        Index("ix_options_stock_ts", "stock_id", "timestamp"),
    )

    stock = relationship("Stock", back_populates="options")


class ScannerResult(Base):
    """Scanner results (persistent audit trail)."""
    __tablename__ = "scanner_results"

    id = Column(BigInteger, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    scanner_name = Column(String(255), nullable=False)
    result_metadata = Column(JSONB, default=dict)  # callable — not a shared mutable default
    matched_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_scanner_results_name_ts", "scanner_name", "matched_at"),
        Index("ix_scanner_results_stock_ts", "stock_id", "matched_at"),
    )

    stock = relationship("Stock", back_populates="scanner_results")


class EconomicIndicator(Base):
    """Macro economic indicator releases."""
    __tablename__ = "economic_indicators"

    id = Column(Integer, primary_key=True)
    indicator_name = Column(String(255), nullable=False)
    release_date = Column(DateTime, nullable=False)
    value = Column(NUMERIC(15, 4))
    unit = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "indicator_name", "release_date",
            name="uq_economic_indicator_name_date",
        ),
    )
```

- [x] **Step 4: Run tests to verify models**

```bash
pytest tests/unit/test_db_models.py -v
```

Expected output: `4 passed`

- [x] **Step 5: Commit**

```bash
git add src/db/models.py tests/unit/test_db_models.py
git commit -m "feat: add SQLAlchemy ORM models with EconomicIndicator, fixed JSONB default, B-tree index"
```

---

### Task 5: Alembic migrations setup

**Files:**
- Modify: `pyproject.toml` (alembic already added in Task 1)
- Create: `alembic.ini` (via alembic init)
- Create: `src/db/migrations/` (via alembic init)

- [x] **Step 1: Install alembic and initialize migrations directory**

```bash
pip install alembic
alembic init src/db/migrations
```

- [x] **Step 2: Update alembic.ini to point at migrations directory**

Edit `alembic.ini`, set:

```ini
script_location = src/db/migrations
```

- [x] **Step 3: Update src/db/migrations/env.py to use project models and get_config()**

```python
# src/db/migrations/env.py  (replace the relevant sections)
import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.db.models import Base  # noqa: E402
from src.config import get_config  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    return get_config().DATABASE_URL


def run_migrations_offline() -> None:
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
```

- [x] **Step 4: Generate initial migration**

```bash
alembic revision --autogenerate -m "initial schema"
```

- [x] **Step 5: Verify migration file was created**

```bash
ls src/db/migrations/versions/
```

Expected output: a `.py` file with `initial_schema` in the name.

- [x] **Step 6: Commit**

```bash
git add alembic.ini src/db/migrations/
git commit -m "feat: add Alembic migrations wired to get_config() and ORM Base"
```

---

## Phase 3: Data Provider Abstraction

### Task 6: DataProvider validation module

**Files:**
- Create: `src/data_provider/validation.py`
- Create: `tests/unit/test_data_provider_validation.py`

- [x] **Step 1: Write failing tests for validation**

```python
# tests/unit/test_data_provider_validation.py
import pytest
from src.data_provider.validation import validate_symbol, validate_resolution
from src.data_provider.exceptions import SymbolNotFoundError, DataProviderError


def test_validate_symbol_valid():
    assert validate_symbol("AAPL") == "AAPL"
    assert validate_symbol("BRK") == "BRK"


def test_validate_symbol_invalid():
    with pytest.raises(SymbolNotFoundError):
        validate_symbol("aapl")  # lowercase
    with pytest.raises(SymbolNotFoundError):
        validate_symbol("TOOLONGSYMBOL")  # > 10 chars
    with pytest.raises(SymbolNotFoundError):
        validate_symbol("12AB")  # starts with digit
    with pytest.raises(SymbolNotFoundError):
        validate_symbol("")  # empty


def test_validate_resolution_valid():
    assert validate_resolution("5m") == "5m"
    assert validate_resolution("15m") == "15m"
    assert validate_resolution("1h") == "1h"


def test_validate_resolution_invalid():
    with pytest.raises(DataProviderError):
        validate_resolution("1d")
    with pytest.raises(DataProviderError):
        validate_resolution("30m")
    with pytest.raises(DataProviderError):
        validate_resolution("")
```

- [x] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_data_provider_validation.py::test_validate_symbol_valid -v
```

Expected output: `FAILED — validate_symbol not defined`

- [x] **Step 3: Implement validation.py**

```python
# src/data_provider/validation.py
import re
from src.data_provider.exceptions import SymbolNotFoundError, DataProviderError

VALID_RESOLUTIONS = frozenset({"5m", "15m", "1h"})
_SYMBOL_RE = re.compile(r'^[A-Z]{1,10}$')


def validate_symbol(symbol: str) -> str:
    """Validate and return the symbol, or raise SymbolNotFoundError."""
    if not _SYMBOL_RE.match(symbol):
        raise SymbolNotFoundError(f"Invalid symbol format: {symbol!r}")
    return symbol


def validate_resolution(resolution: str) -> str:
    """Validate and return the resolution, or raise DataProviderError."""
    if resolution not in VALID_RESOLUTIONS:
        raise DataProviderError(
            f"Invalid resolution {resolution!r}. Must be one of: {sorted(VALID_RESOLUTIONS)}"
        )
    return resolution
```

- [x] **Step 4: Run tests**

```bash
pytest tests/unit/test_data_provider_validation.py -v
```

Expected output: `4 passed`

- [x] **Step 5: Commit**

```bash
git add src/data_provider/validation.py tests/unit/test_data_provider_validation.py
git commit -m "feat: add input validation for symbol and resolution"
```

---

### Task 7: DataProvider base class and exceptions

**Files:**
- Create: `src/data_provider/__init__.py`
- Create: `src/data_provider/base.py`
- Create: `src/data_provider/exceptions.py`
- Create: `tests/unit/test_data_provider_base.py`

- [x] **Step 1: Write failing tests for DataProvider interface**

```python
# tests/unit/test_data_provider_base.py
import pytest
from abc import ABC
from datetime import datetime
from src.data_provider.base import DataProvider, Candle, Quote


def test_candle_dataclass():
    candle = Candle(
        timestamp=datetime(2024, 1, 1),
        open=100.0, high=102.0, low=99.0, close=101.0, volume=1000000,
    )
    assert candle.close == 101.0


def test_quote_dataclass():
    quote = Quote(
        timestamp=datetime(2024, 1, 1),
        bid=100.0, ask=100.5, bid_size=1000, ask_size=1000,
        last=100.2, open=99.5, high=101.0, low=99.0, close=100.0,
        volume=5000000, change=0.5, change_pct=0.5,
        week_52_high=120.0, week_52_low=80.0, status="active",
    )
    assert quote.bid < quote.ask


def test_data_provider_is_abstract():
    with pytest.raises(TypeError):
        DataProvider()
```

- [x] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_data_provider_base.py::test_candle_dataclass -v
```

Expected output: `FAILED — Candle not defined`

- [x] **Step 3: Implement exceptions.py**

```python
# src/data_provider/exceptions.py
class DataProviderError(Exception):
    """Base exception for data provider errors."""
    pass


class RateLimitError(DataProviderError):
    """Raised when API rate limit is exceeded."""
    pass


class SymbolNotFoundError(DataProviderError):
    """Raised when symbol is not found."""
    pass


class APIConnectionError(DataProviderError):
    """Raised when API connection fails."""
    pass
```

- [x] **Step 4: Implement base.py with dataclasses and abstract interface**

```python
# src/data_provider/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Candle:
    """OHLCV candle."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class Quote:
    """Realtime quote with intraday summary."""
    timestamp: datetime
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    change: float
    change_pct: float
    week_52_high: float
    week_52_low: float
    status: str


@dataclass
class NewsArticle:
    """News article."""
    symbol: str
    headline: str
    content: str
    source: str
    publication_date: datetime


@dataclass
class Earning:
    """Earnings record."""
    symbol: str
    fiscal_year: int
    fiscal_quarter: int
    earnings_date: datetime
    report_date: datetime
    report_time: str
    currency: str
    reported_eps: float
    estimated_eps: float


class DataProvider(ABC):
    """Abstract interface for market data providers."""

    @abstractmethod
    def get_daily_candles(
        self, symbol: str, from_date: datetime, to_date: datetime,
    ) -> List[Candle]:
        pass

    @abstractmethod
    def get_intraday_candles(
        self, symbol: str, resolution: str, from_date: datetime, to_date: datetime,
    ) -> List[Candle]:
        pass

    @abstractmethod
    def get_realtime_quote(self, symbol: str) -> Quote:
        pass

    @abstractmethod
    def get_earnings_history(
        self, symbol: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[Earning]:
        pass

    @abstractmethod
    def get_news(
        self, symbol: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        countback: Optional[int] = None,
    ) -> List[NewsArticle]:
        pass
```

- [x] **Step 5: Create __init__.py**

```python
# src/data_provider/__init__.py
from src.data_provider.base import DataProvider, Candle, Quote, NewsArticle, Earning
from src.data_provider.exceptions import (
    DataProviderError, RateLimitError, SymbolNotFoundError, APIConnectionError,
)

__all__ = [
    "DataProvider", "Candle", "Quote", "NewsArticle", "Earning",
    "DataProviderError", "RateLimitError", "SymbolNotFoundError", "APIConnectionError",
]
```

- [x] **Step 6: Run tests**

```bash
pytest tests/unit/test_data_provider_base.py -v
```

Expected output: `3 passed`

- [x] **Step 7: Commit**

```bash
git add src/data_provider/ tests/unit/test_data_provider_base.py
git commit -m "feat: add abstract DataProvider interface with dataclasses and exceptions"
```

---

### Task 8: MarketData.app provider (with validation calls, timeouts, retry)

**Files:**
- Create: `src/data_provider/marketdata_app.py`
- Create: `tests/unit/test_marketdata_provider.py`

- [x] **Step 1: Write failing tests for MarketDataAppProvider**

```python
# tests/unit/test_marketdata_provider.py
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from src.data_provider.marketdata_app import MarketDataAppProvider
from src.data_provider.base import Candle
from src.data_provider.exceptions import SymbolNotFoundError, DataProviderError


def test_marketdata_provider_init():
    provider = MarketDataAppProvider(api_token="test_token", max_retries=3, retry_backoff_base=0)
    assert provider.api_token == "test_token"
    assert provider.base_url == "https://api.marketdata.app/v1"


def test_validate_symbol_called_on_get_daily_candles():
    provider = MarketDataAppProvider(api_token="test_token", max_retries=1, retry_backoff_base=0)
    with pytest.raises(SymbolNotFoundError):
        provider.get_daily_candles("invalid!", datetime(2024, 1, 1), datetime(2024, 1, 31))


def test_validate_resolution_called_on_get_intraday():
    provider = MarketDataAppProvider(api_token="test_token", max_retries=1, retry_backoff_base=0)
    with pytest.raises(DataProviderError):
        provider.get_intraday_candles("AAPL", "1d", datetime(2024, 1, 1), datetime(2024, 1, 31))


@patch("src.data_provider.marketdata_app.requests.Session")
def test_get_daily_candles_parsing(mock_session_class):
    mock_session = Mock()
    mock_session_class.return_value = mock_session

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"t": "2024-01-01T00:00:00", "o": 150.0, "h": 152.0, "l": 149.0, "c": 151.0, "v": 1000000}
        ]
    }
    mock_response.raise_for_status = Mock()
    mock_session.get.return_value = mock_response

    provider = MarketDataAppProvider(api_token="test_token", max_retries=1, retry_backoff_base=0)
    candles = provider.get_daily_candles("AAPL", datetime(2024, 1, 1), datetime(2024, 1, 31))

    assert len(candles) == 1
    assert candles[0].close == 151.0
    # Verify timeout was passed
    call_kwargs = mock_session.get.call_args
    assert call_kwargs[1].get("timeout") == (5, 30)


@patch("src.data_provider.marketdata_app.requests.Session")
def test_request_uses_timeout(mock_session_class):
    mock_session = Mock()
    mock_session_class.return_value = mock_session
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"results": []}
    mock_session.get.return_value = mock_response

    provider = MarketDataAppProvider(api_token="test_token", max_retries=1, retry_backoff_base=0)
    provider.get_daily_candles("AAPL", datetime(2024, 1, 1), datetime(2024, 1, 31))

    call_kwargs = mock_session.get.call_args
    assert call_kwargs[1].get("timeout") == (5, 30)
```

- [x] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_marketdata_provider.py::test_marketdata_provider_init -v
```

Expected output: `FAILED — MarketDataAppProvider not defined`

- [x] **Step 3: Implement MarketDataAppProvider with validation, timeouts, and retry**

```python
# src/data_provider/marketdata_app.py
import requests
import time
import logging
from datetime import datetime
from typing import List, Optional

from src.data_provider.base import DataProvider, Candle, Quote, NewsArticle, Earning
from src.data_provider.exceptions import APIConnectionError, RateLimitError, SymbolNotFoundError
from src.data_provider.validation import validate_symbol, validate_resolution

logger = logging.getLogger(__name__)


class MarketDataAppProvider(DataProvider):
    """MarketData.app implementation with retry logic, validation, and timeouts."""

    def __init__(
        self,
        api_token: str,
        max_retries: int = 5,
        retry_backoff_base: int = 1,
    ):
        self.base_url = "https://api.marketdata.app/v1"
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_token}"})
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base

    def _request_with_retry(self, url: str, **kwargs) -> dict:
        """Make GET request with exponential backoff. Always passes timeout=(5, 30)."""
        last_error = None
        kwargs.setdefault("timeout", (5, 30))

        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, **kwargs)
                resp.raise_for_status()
                return resp.json()

            except requests.exceptions.HTTPError as e:
                if resp.status_code == 429:
                    raise RateLimitError(f"API rate limit exceeded: {e}")
                elif resp.status_code == 404:
                    raise SymbolNotFoundError(f"Symbol not found: {e}")
                last_error = e

            except requests.exceptions.RequestException as e:
                last_error = e

            if attempt < self.max_retries - 1:
                wait_time = self.retry_backoff_base ** attempt
                time.sleep(wait_time)

        raise APIConnectionError(f"Failed after {self.max_retries} retries: {last_error}")

    def get_daily_candles(
        self, symbol: str, from_date: datetime, to_date: datetime,
    ) -> List[Candle]:
        validate_symbol(symbol)
        url = f"{self.base_url}/stocks/candles/1d/{symbol}"
        params = {"from": from_date.isoformat(), "to": to_date.isoformat(), "feed": "cached"}
        data = self._request_with_retry(url, params=params)
        return [
            Candle(
                timestamp=datetime.fromisoformat(r["t"]),
                open=float(r["o"]), high=float(r["h"]),
                low=float(r["l"]), close=float(r["c"]),
                volume=int(r["v"]),
            )
            for r in data.get("results", [])
        ]

    def get_intraday_candles(
        self, symbol: str, resolution: str, from_date: datetime, to_date: datetime,
    ) -> List[Candle]:
        validate_symbol(symbol)
        validate_resolution(resolution)
        url = f"{self.base_url}/stocks/candles/{resolution}/{symbol}"
        params = {"from": from_date.isoformat(), "to": to_date.isoformat(), "feed": "cached"}
        data = self._request_with_retry(url, params=params)
        return [
            Candle(
                timestamp=datetime.fromisoformat(r["t"]),
                open=float(r["o"]), high=float(r["h"]),
                low=float(r["l"]), close=float(r["c"]),
                volume=int(r["v"]),
            )
            for r in data.get("results", [])
        ]

    def get_realtime_quote(self, symbol: str) -> Quote:
        validate_symbol(symbol)
        url = f"{self.base_url}/stocks/quotes/{symbol}"
        data = self._request_with_retry(url, params={"feed": "live"})
        result = data["results"][0]
        return Quote(
            timestamp=datetime.fromisoformat(result["updated"]),
            bid=float(result["bid"]), ask=float(result["ask"]),
            bid_size=int(result["bidSize"]), ask_size=int(result["askSize"]),
            last=float(result["last"]),
            open=float(result["o"]), high=float(result["h"]),
            low=float(result["l"]), close=float(result["c"]),
            volume=int(result["volume"]),
            change=float(result["change"]), change_pct=float(result["changepct"]),
            week_52_high=float(result["52weekHigh"]),
            week_52_low=float(result["52weekLow"]),
            status=result["status"],
        )

    def get_earnings_history(
        self, symbol: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[Earning]:
        validate_symbol(symbol)
        url = f"{self.base_url}/stocks/earnings/{symbol}"
        params = {}
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()
        data = self._request_with_retry(url, params=params)
        return [
            Earning(
                symbol=symbol,
                fiscal_year=int(r["fiscalYear"]),
                fiscal_quarter=int(r["fiscalQuarter"]),
                earnings_date=datetime.fromisoformat(r["date"]),
                report_date=datetime.fromisoformat(r["reportDate"]),
                report_time=r["reportTime"],
                currency=r["currency"],
                reported_eps=float(r["reportedEPS"]),
                estimated_eps=float(r["estimatedEPS"]),
            )
            for r in data.get("results", [])
        ]

    def get_news(
        self, symbol: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        countback: Optional[int] = None,
    ) -> List[NewsArticle]:
        validate_symbol(symbol)
        url = f"{self.base_url}/stocks/news/{symbol}"
        params = {}
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()
        if countback:
            params["countback"] = countback
        data = self._request_with_retry(url, params=params)
        headlines = data.get("headline", [])
        contents = data.get("content", [])
        sources = data.get("source", [])
        pub_dates = data.get("publicationDate", [])
        return [
            NewsArticle(
                symbol=symbol,
                headline=headline,
                content=contents[i] if i < len(contents) else "",
                source=sources[i] if i < len(sources) else "",
                publication_date=datetime.fromisoformat(pub_dates[i]),
            )
            for i, headline in enumerate(headlines)
        ]
```

- [x] **Step 4: Run tests**

```bash
pytest tests/unit/test_marketdata_provider.py -v
```

Expected output: `5 passed`

- [x] **Step 5: Commit**

```bash
git add src/data_provider/marketdata_app.py tests/unit/test_marketdata_provider.py
git commit -m "feat: implement MarketData.app provider with validation, timeouts, and retry"
```

---

## Phase 4: Indicators Framework

### Task 9: Indicator base class and IndicatorCache

**Files:**
- Create: `src/scanner/__init__.py`
- Create: `src/scanner/indicators/__init__.py`
- Create: `src/scanner/indicators/base.py`
- Create: `src/scanner/indicators/cache.py`
- Create: `src/scanner/context.py`
- Create: `tests/unit/test_indicator_cache.py`

- [x] **Step 1: Write failing tests for IndicatorCache**

```python
# tests/unit/test_indicator_cache.py
import pytest
import numpy as np
from datetime import datetime
from src.scanner.indicators.cache import IndicatorCache
from src.scanner.indicators.base import Indicator
from src.data_provider.base import Candle


class MockIndicator(Indicator):
    def compute(self, candles, **kwargs):
        return np.array([c.close for c in candles])


def make_candles(n=3):
    return [Candle(datetime.now(), 100 + i, 102 + i, 99 + i, 101 + i, 1000) for i in range(n)]


def test_indicator_cache_computes_once():
    cache = IndicatorCache({"mock": MockIndicator()})
    candles = make_candles(2)
    result1 = cache.get_or_compute("mock", candles)
    result2 = cache.get_or_compute("mock", candles)
    assert result1 is result2
    assert len(result1) == 2


def test_indicator_cache_different_kwargs():
    cache = IndicatorCache({"mock": MockIndicator()})
    candles = make_candles(1)
    result1 = cache.get_or_compute("mock", candles, period=10)
    result2 = cache.get_or_compute("mock", candles, period=20)
    assert result1 is not result2


def test_indicator_cache_clear():
    cache = IndicatorCache({"mock": MockIndicator()})
    candles = make_candles(2)
    r1 = cache.get_or_compute("mock", candles)
    cache.clear()
    r2 = cache.get_or_compute("mock", candles)
    assert r1 is not r2
```

- [x] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_indicator_cache.py::test_indicator_cache_computes_once -v
```

Expected output: `FAILED — IndicatorCache not defined`

- [x] **Step 3: Implement Indicator base class**

```python
# src/scanner/indicators/base.py
from abc import ABC, abstractmethod
import numpy as np
from typing import List
from src.data_provider.base import Candle


class Indicator(ABC):
    """Abstract base for all technical indicators."""

    @abstractmethod
    def compute(self, candles: List[Candle], **kwargs) -> np.ndarray:
        """Compute indicator values and return a numpy array."""
        pass
```

- [x] **Step 4: Implement IndicatorCache**

```python
# src/scanner/indicators/cache.py
from typing import Dict, Tuple, List
import numpy as np
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class IndicatorCache:
    """Cache for indicators computed during EOD run — avoids recomputation."""

    def __init__(self, indicators_registry: Dict[str, Indicator]):
        self.registry = indicators_registry
        self._cache: Dict[Tuple, np.ndarray] = {}

    def get_or_compute(self, name: str, candles: List[Candle], **kwargs) -> np.ndarray:
        """Return cached result or compute and cache it."""
        cache_key = (name, tuple(sorted(kwargs.items())))
        if cache_key in self._cache:
            return self._cache[cache_key]
        indicator = self.registry[name]
        result = indicator.compute(candles, **kwargs)
        self._cache[cache_key] = result
        return result

    def clear(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
```

- [x] **Step 5: Implement ScanContext**

```python
# src/scanner/context.py
from dataclasses import dataclass
from typing import Dict, List
import numpy as np
from src.data_provider.base import Candle
from src.scanner.indicators.cache import IndicatorCache


@dataclass
class ScanContext:
    """Context passed to scanners during execution."""
    stock_id: int
    symbol: str
    daily_candles: List[Candle]
    intraday_candles: Dict[str, List[Candle]]  # {'5m': [...], '15m': [...]}
    indicator_cache: IndicatorCache

    def get_indicator(self, name: str, **kwargs) -> np.ndarray:
        """Retrieve (or calculate once) an indicator from the cache."""
        return self.indicator_cache.get_or_compute(name, self.daily_candles, **kwargs)
```

- [x] **Step 6: Create __init__.py files**

```python
# src/scanner/__init__.py
```

```python
# src/scanner/indicators/__init__.py
from src.scanner.indicators.base import Indicator
from src.scanner.indicators.cache import IndicatorCache

__all__ = ["Indicator", "IndicatorCache"]
```

- [x] **Step 7: Run tests**

```bash
pytest tests/unit/test_indicator_cache.py -v
```

Expected output: `3 passed`

- [x] **Step 8: Commit**

```bash
git add src/scanner/ tests/unit/test_indicator_cache.py
git commit -m "feat: add indicator base class, IndicatorCache, and ScanContext"
```

---

### Task 10: Moving average indicators (SMA, EMA with fixed warmup, WMA)

**Files:**
- Create: `src/scanner/indicators/moving_averages.py`
- Create: `tests/unit/test_indicators.py` (partial — extended in Tasks 11–13)

- [x] **Step 1: Write failing tests for moving averages**

```python
# tests/unit/test_indicators.py
import pytest
import numpy as np
from datetime import datetime
from src.data_provider.base import Candle
from src.scanner.indicators.moving_averages import SMA, EMA, WMA
from src.scanner.indicators.momentum import RSI, MACD
from src.scanner.indicators.volatility import BollingerBands, ATR
from src.scanner.indicators.support_resistance import SupportResistance
from src.scanner.indicators.patterns.breakouts import BreakoutDetector
from src.scanner.indicators.patterns.candlestick import CandlestickPatterns


def make_candles(closes, highs=None, lows=None):
    if highs is None:
        highs = [c + 1 for c in closes]
    if lows is None:
        lows = [c - 1 for c in closes]
    return [
        Candle(datetime(2024, 1, i + 1), c, h, l, c, 1000)
        for i, (c, h, l) in enumerate(zip(closes, highs, lows))
    ]


# --- SMA ---
def test_sma_calculation():
    candles = make_candles([100, 101, 102, 103, 104])
    result = SMA().compute(candles, period=3)
    np.testing.assert_array_almost_equal(result, [101, 102, 103])


def test_sma_too_few_candles():
    candles = make_candles([100, 101])
    assert len(SMA().compute(candles, period=5)) == 0


# --- EMA ---
def test_ema_length_matches_sma():
    closes = list(range(100, 160))
    candles = make_candles(closes)
    sma = SMA().compute(candles, period=10)
    ema = EMA().compute(candles, period=10)
    # Both return len(closes) - period + 1 values
    assert len(ema) == len(sma)


def test_ema_seeded_with_sma():
    closes = [float(i) for i in range(1, 21)]
    candles = make_candles(closes)
    ema = EMA().compute(candles, period=5)
    # First value must equal SMA of first 5 values = mean([1,2,3,4,5]) = 3.0
    assert abs(ema[0] - 3.0) < 1e-9


def test_ema_too_few_candles():
    candles = make_candles([100, 101])
    assert len(EMA().compute(candles, period=5)) == 0


# --- WMA ---
def test_wma_calculation():
    candles = make_candles([10, 20, 30])
    result = WMA().compute(candles, period=3)
    # WMA([10,20,30], weights=[1,2,3]) = (10*1 + 20*2 + 30*3) / 6 = 140/6
    assert abs(result[0] - 140 / 6) < 1e-6


# --- RSI ---
def test_rsi_range():
    closes = [100 + (i % 7) * 1.5 for i in range(30)]
    candles = make_candles(closes)
    result = RSI().compute(candles, period=14)
    assert len(result) > 0
    assert all(0 <= v <= 100 for v in result)


def test_rsi_seeded_first_value():
    # If all gains, RSI should be 100
    closes = [float(i) for i in range(1, 32)]
    candles = make_candles(closes)
    result = RSI().compute(candles, period=14)
    assert abs(result[0] - 100.0) < 1e-6


def test_rsi_too_few_candles():
    candles = make_candles([100, 101])
    assert len(RSI().compute(candles, period=14)) == 0


# --- BollingerBands ---
def test_bollinger_bands_shape():
    closes = [float(100 + i % 5) for i in range(30)]
    candles = make_candles(closes)
    result = BollingerBands().compute(candles, period=20)
    assert result.shape[1] == 3  # (upper, middle, lower)
    assert result.shape[0] == len(closes) - 20 + 1


def test_bollinger_bands_upper_gt_lower():
    closes = [float(100 + i % 10) for i in range(30)]
    candles = make_candles(closes)
    result = BollingerBands().compute(candles, period=20)
    assert np.all(result[:, 0] >= result[:, 2])  # upper >= lower


def test_bollinger_bands_too_few():
    candles = make_candles([100, 101])
    result = BollingerBands().compute(candles, period=20)
    assert result.shape == (0, 3)


# --- ATR ---
def test_atr_length():
    closes = list(range(100, 130))
    highs = [c + 2 for c in closes]
    lows = [c - 2 for c in closes]
    candles = make_candles(closes, highs, lows)
    result = ATR().compute(candles, period=14)
    expected_len = len(candles) - 14 - 1 + 1  # len(tr) = n-1, then rolling mean
    assert len(result) == expected_len


def test_atr_too_few():
    candles = make_candles([100, 101, 102])
    assert len(ATR().compute(candles, period=14)) == 0


# --- SupportResistance ---
def test_support_resistance_returns_values():
    closes = [100, 102, 99, 104, 101, 105, 100, 106, 102, 107]
    candles = make_candles(closes)
    result = SupportResistance().compute(candles)
    assert len(result) > 0


# --- BreakoutDetector ---
def test_breakout_detector_signals_above():
    # First 20 candles hover at 100, then one closes above
    closes = [100.0] * 20 + [105.0]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    candles = make_candles(closes, highs, lows)
    result = BreakoutDetector().compute(candles, lookback=20)
    assert result[-1] == 1.0  # breakout above resistance


def test_breakout_detector_too_few():
    candles = make_candles([100.0] * 5)
    result = BreakoutDetector().compute(candles, lookback=20)
    assert len(result) == 0


# --- CandlestickPatterns ---
def test_candlestick_doji():
    # High and low span 10, body spans 0.5 (body/range < 0.1 → doji)
    candles = [
        Candle(datetime(2024, 1, 1), 100, 100, 100, 100, 1000),  # seed
        Candle(datetime(2024, 1, 2), 100.0, 105.0, 95.0, 100.4, 1000),  # doji
    ]
    result = CandlestickPatterns().compute(candles)
    assert result[1] == 2  # doji


def test_candlestick_too_few():
    candles = make_candles([100.0])
    result = CandlestickPatterns().compute(candles)
    assert len(result) == 0
```

- [x] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_indicators.py::test_sma_calculation -v
```

Expected output: `FAILED — SMA not defined`

- [x] **Step 3: Implement moving_averages.py**

```python
# src/scanner/indicators/moving_averages.py
import numpy as np
from typing import List
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class SMA(Indicator):
    """Simple Moving Average."""

    def compute(self, candles: List[Candle], period: int = 50, **kwargs) -> np.ndarray:
        closes = np.array([c.close for c in candles], dtype=float)
        if len(closes) < period:
            return np.array([])
        weights = np.ones(period) / period
        return np.convolve(closes, weights, mode="valid")


class EMA(Indicator):
    """Exponential Moving Average — seeded with SMA of first `period` values."""

    def compute(self, candles: List[Candle], period: int = 50, **kwargs) -> np.ndarray:
        closes = np.array([c.close for c in candles], dtype=float)
        if len(closes) < period:
            return np.array([])

        alpha = 2 / (period + 1)
        # Seed with SMA of first 'period' values for accurate warmup
        ema_values = [np.mean(closes[:period])]
        for close in closes[period:]:
            ema_values.append(alpha * close + (1 - alpha) * ema_values[-1])

        # Returns len(closes) - period + 1 values — same as SMA 'valid'
        return np.array(ema_values)


class WMA(Indicator):
    """Weighted Moving Average."""

    def compute(self, candles: List[Candle], period: int = 50, **kwargs) -> np.ndarray:
        closes = np.array([c.close for c in candles], dtype=float)
        if len(closes) < period:
            return np.array([])
        weights = np.arange(1, period + 1)
        return np.convolve(closes, weights[::-1], mode="valid") / weights.sum()
```

- [x] **Step 4: Run moving average tests**

```bash
pytest tests/unit/test_indicators.py -k "sma or ema or wma" -v
```

Expected output: `6 passed`

- [x] **Step 5: Commit**

```bash
git add src/scanner/indicators/moving_averages.py tests/unit/test_indicators.py
git commit -m "feat: implement SMA, EMA (fixed SMA-seeded warmup), WMA indicators"
```

---

### Task 11: Momentum indicators (RSI with fixed seed, MACD)

**Files:**
- Create: `src/scanner/indicators/momentum.py`

- [x] **Step 1: Run RSI tests to verify they fail**

```bash
pytest tests/unit/test_indicators.py -k "rsi" -v
```

Expected output: `FAILED — RSI not defined`

- [x] **Step 2: Implement momentum.py**

```python
# src/scanner/indicators/momentum.py
import numpy as np
from typing import List
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class RSI(Indicator):
    """Relative Strength Index — first value seeded from initial average gain/loss."""

    def compute(self, candles: List[Candle], period: int = 14, **kwargs) -> np.ndarray:
        closes = np.array([c.close for c in candles], dtype=float)
        if len(closes) < period + 1:
            return np.array([])

        deltas = np.diff(closes)
        gains = np.maximum(deltas, 0)
        losses = np.abs(np.minimum(deltas, 0))

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        rsi_values = []

        # Seed first RSI value from initial averages
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rsi_values.append(100 - (100 / (1 + avg_gain / avg_loss)))

        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                rsi_values.append(100.0)
            else:
                rsi_values.append(100 - (100 / (1 + avg_gain / avg_loss)))

        return np.array(rsi_values)


class MACD(Indicator):
    """MACD (Moving Average Convergence Divergence)."""

    def compute(
        self, candles: List[Candle],
        fast_period: int = 12, slow_period: int = 26, signal_period: int = 9,
        **kwargs,
    ) -> np.ndarray:
        closes = np.array([c.close for c in candles], dtype=float)
        fast_ema = self._ema(closes, fast_period)
        slow_ema = self._ema(closes, slow_period)
        min_len = min(len(fast_ema), len(slow_ema))
        return fast_ema[-min_len:] - slow_ema[-min_len:]

    @staticmethod
    def _ema(values: np.ndarray, period: int) -> np.ndarray:
        if len(values) < period:
            return np.array([])
        alpha = 2 / (period + 1)
        ema = [np.mean(values[:period])]
        for v in values[period:]:
            ema.append(alpha * v + (1 - alpha) * ema[-1])
        return np.array(ema)
```

- [x] **Step 3: Run momentum tests**

```bash
pytest tests/unit/test_indicators.py -k "rsi or macd" -v
```

Expected output: `3 passed`

- [x] **Step 4: Commit**

```bash
git add src/scanner/indicators/momentum.py
git commit -m "feat: implement RSI (fixed seeded first value) and MACD indicators"
```

---

### Task 12: Volatility indicators (BollingerBands, ATR)

**Files:**
- Create: `src/scanner/indicators/volatility.py`

- [x] **Step 1: Run volatility tests to verify they fail**

```bash
pytest tests/unit/test_indicators.py -k "bollinger or atr" -v
```

Expected output: `FAILED — BollingerBands not defined`

- [x] **Step 2: Implement volatility.py**

```python
# src/scanner/indicators/volatility.py
import numpy as np
from typing import List
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class BollingerBands(Indicator):
    """Bollinger Bands: returns (upper, middle, lower) as shape (n, 3) array."""

    def compute(
        self, candles: List[Candle], period: int = 20, std_dev: float = 2.0, **kwargs
    ) -> np.ndarray:
        closes = np.array([c.close for c in candles], dtype=float)
        if len(closes) < period:
            return np.array([]).reshape(0, 3)

        n = len(closes) - period + 1
        upper, middle, lower = np.zeros(n), np.zeros(n), np.zeros(n)

        for i in range(n):
            window = closes[i:i + period]
            mean = np.mean(window)
            std = np.std(window, ddof=0)
            middle[i] = mean
            upper[i] = mean + std_dev * std
            lower[i] = mean - std_dev * std

        return np.column_stack([upper, middle, lower])


class ATR(Indicator):
    """Average True Range."""

    def compute(self, candles: List[Candle], period: int = 14, **kwargs) -> np.ndarray:
        if len(candles) < period + 1:
            return np.array([])

        highs = np.array([c.high for c in candles], dtype=float)
        lows = np.array([c.low for c in candles], dtype=float)
        closes = np.array([c.close for c in candles], dtype=float)

        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1]),
            ),
        )

        n = len(tr) - period + 1
        return np.array([np.mean(tr[i:i + period]) for i in range(n)])
```

- [x] **Step 3: Run volatility tests**

```bash
pytest tests/unit/test_indicators.py -k "bollinger or atr" -v
```

Expected output: `5 passed`

- [x] **Step 4: Commit**

```bash
git add src/scanner/indicators/volatility.py
git commit -m "feat: implement BollingerBands and ATR volatility indicators"
```

---

### Task 13: Pattern indicators (BreakoutDetector, CandlestickPatterns)

**Files:**
- Create: `src/scanner/indicators/patterns/__init__.py`
- Create: `src/scanner/indicators/patterns/breakouts.py`
- Create: `src/scanner/indicators/patterns/candlestick.py`
- Create: `src/scanner/indicators/support_resistance.py`

- [x] **Step 1: Run pattern tests to verify they fail**

```bash
pytest tests/unit/test_indicators.py -k "breakout or candlestick or support" -v
```

Expected output: `FAILED — BreakoutDetector not defined`

- [x] **Step 2: Implement breakouts.py**

```python
# src/scanner/indicators/patterns/breakouts.py
import numpy as np
from typing import List
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class BreakoutDetector(Indicator):
    """Returns 1.0=breakout above resistance, -1.0=breakdown below support, 0=none."""

    def compute(self, candles: List[Candle], lookback: int = 20, **kwargs) -> np.ndarray:
        closes = np.array([c.close for c in candles], dtype=float)
        highs = np.array([c.high for c in candles], dtype=float)
        lows = np.array([c.low for c in candles], dtype=float)

        if len(closes) < lookback + 1:
            return np.array([])

        n = len(closes) - lookback
        signals = np.zeros(n)

        for i in range(n):
            prior_high = np.max(highs[i:i + lookback])
            prior_low = np.min(lows[i:i + lookback])
            current_close = closes[i + lookback]

            if current_close > prior_high:
                signals[i] = 1.0
            elif current_close < prior_low:
                signals[i] = -1.0

        return signals
```

- [x] **Step 3: Implement candlestick.py**

```python
# src/scanner/indicators/patterns/candlestick.py
import numpy as np
from typing import List
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class CandlestickPatterns(Indicator):
    """Pattern codes: 1=bullish_engulf, -1=bearish_engulf, 2=doji, 0=none."""

    def compute(self, candles: List[Candle], **kwargs) -> np.ndarray:
        if len(candles) < 2:
            return np.array([])

        signals = np.zeros(len(candles))

        for i in range(1, len(candles)):
            prev, curr = candles[i - 1], candles[i]
            curr_range = curr.high - curr.low
            curr_body = abs(curr.close - curr.open)

            if curr_range > 0 and curr_body / curr_range < 0.1:
                signals[i] = 2  # Doji
            elif (
                prev.close < prev.open
                and curr.close > curr.open
                and curr.open <= prev.close
                and curr.close >= prev.open
            ):
                signals[i] = 1  # Bullish engulfing
            elif (
                prev.close > prev.open
                and curr.close < curr.open
                and curr.open >= prev.close
                and curr.close <= prev.open
            ):
                signals[i] = -1  # Bearish engulfing

        return signals
```

- [x] **Step 4: Create patterns/__init__.py**

```python
# src/scanner/indicators/patterns/__init__.py
from src.scanner.indicators.patterns.breakouts import BreakoutDetector
from src.scanner.indicators.patterns.candlestick import CandlestickPatterns

__all__ = ["BreakoutDetector", "CandlestickPatterns"]
```

- [x] **Step 5: Implement support_resistance.py**

```python
# src/scanner/indicators/support_resistance.py
import numpy as np
from typing import List
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class SupportResistance(Indicator):
    """Detect support and resistance levels via rolling min/max."""

    def compute(self, candles: List[Candle], lookback: int = 20, **kwargs) -> np.ndarray:
        lows = np.array([c.low for c in candles], dtype=float)
        highs = np.array([c.high for c in candles], dtype=float)

        if len(lows) < lookback:
            return np.array([])

        support = np.array([np.min(lows[max(0, i - lookback):i + 1]) for i in range(len(lows))])
        resistance = np.array([np.max(highs[max(0, i - lookback):i + 1]) for i in range(len(highs))])

        return (support + resistance) / 2
```

- [x] **Step 6: Run all indicator tests**

```bash
pytest tests/unit/test_indicators.py -v
```

Expected output: all indicator tests pass

- [x] **Step 7: Commit**

```bash
git add src/scanner/indicators/ tests/unit/test_indicators.py
git commit -m "feat: implement pattern indicators (BreakoutDetector, CandlestickPatterns) and SupportResistance"
```

---

## Phase 5: Scanners Framework

### Task 14: Support/resistance indicator (already added in Task 13)

> **Note:** SupportResistance was implemented in Task 13 Step 5. This task is satisfied.

---

### Task 15: Scanner base class (ScanResult here only), ScanContext, registry

**Files:**
- Create: `src/scanner/base.py`
- Create: `src/scanner/registry.py`
- Create: `tests/unit/test_scanners.py`

- [x] **Step 1: Write failing tests for Scanner base and registry**

```python
# tests/unit/test_scanners.py
import pytest
from datetime import datetime
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext
from src.scanner.registry import ScannerRegistry
from src.scanner.indicators.cache import IndicatorCache
from src.data_provider.base import Candle


def test_scan_result_dataclass():
    result = ScanResult(stock_id=1, scanner_name="test_scanner", metadata={"reason": "test"})
    assert result.stock_id == 1
    assert result.scanner_name == "test_scanner"
    assert result.matched_at is not None


def test_scanner_registry_registration():
    registry = ScannerRegistry()

    class TestScanner(Scanner):
        def scan(self, context: ScanContext):
            return []

    registry.register("test", TestScanner())
    assert registry.get("test") is not None


def test_scanner_registry_list_empty():
    registry = ScannerRegistry()
    assert len(registry.list()) == 0


def test_scanner_registry_multiple():
    registry = ScannerRegistry()

    class NoopScanner(Scanner):
        def scan(self, context: ScanContext):
            return []

    registry.register("a", NoopScanner())
    registry.register("b", NoopScanner())
    assert len(registry.list()) == 2
```

- [x] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_scanners.py::test_scan_result_dataclass -v
```

Expected output: `FAILED — ScanResult not defined`

- [x] **Step 3: Implement Scanner base class (ScanResult lives HERE only)**

```python
# src/scanner/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List
from datetime import datetime
from src.scanner.context import ScanContext


@dataclass
class ScanResult:
    """Result from a scanner — single source of truth (not duplicated in output/base.py)."""
    stock_id: int
    scanner_name: str
    metadata: dict
    matched_at: datetime = field(default_factory=datetime.utcnow)


class Scanner(ABC):
    """Abstract base for all scanners."""

    @abstractmethod
    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Run scanner against context, return matches."""
        pass
```

- [x] **Step 4: Implement ScannerRegistry**

```python
# src/scanner/registry.py
from typing import Dict
from src.scanner.base import Scanner


class ScannerRegistry:
    """Registry for discovering and loading scanners."""

    def __init__(self):
        self._scanners: Dict[str, Scanner] = {}

    def register(self, name: str, scanner: Scanner) -> None:
        self._scanners[name] = scanner

    def get(self, name: str) -> Scanner:
        return self._scanners.get(name)

    def list(self) -> Dict[str, Scanner]:
        return dict(self._scanners)
```

- [x] **Step 5: Run tests**

```bash
pytest tests/unit/test_scanners.py -v
```

Expected output: `4 passed`

- [x] **Step 6: Commit**

```bash
git add src/scanner/base.py src/scanner/registry.py tests/unit/test_scanners.py
git commit -m "feat: add Scanner base class (ScanResult single-source), ScannerRegistry"
```

---

### Task 16: ScannerExecutor (ORM→dataclass conversion, batch commits, joinedload loading in main)

**Files:**
- Create: `src/scanner/executor.py`

- [x] **Step 1: Write failing test for executor**

```python
# tests/unit/test_scanner_executor.py (append to test_scanners.py)
# (Added inline here for completeness — use the same file)
import pytest
from datetime import datetime
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext
from src.scanner.registry import ScannerRegistry
from src.scanner.executor import ScannerExecutor
from src.scanner.indicators.moving_averages import SMA
from src.scanner.indicators.cache import IndicatorCache
from src.data_provider.base import Candle
from src.output.cli import CLIOutputHandler


class AlwaysMatchScanner(Scanner):
    def scan(self, context: ScanContext):
        return [ScanResult(stock_id=context.stock_id, scanner_name="always", metadata={})]


def make_candles_list(n=10):
    return [Candle(datetime(2024, 1, i + 1), 100 + i, 102 + i, 99 + i, 101 + i, 1000)
            for i in range(n)]


def test_executor_run_eod_returns_results():
    registry = ScannerRegistry()
    registry.register("always", AlwaysMatchScanner())
    indicators = {"sma": SMA()}
    output = CLIOutputHandler()
    executor = ScannerExecutor(registry=registry, indicators_registry=indicators,
                               output_handler=output, db=None)
    stocks = {1: ("AAPL", make_candles_list(50))}
    results = executor.run_eod(stocks)
    assert len(results) == 1
    assert results[0].scanner_name == "always"


def test_executor_to_candles_conversion():
    registry = ScannerRegistry()
    output = CLIOutputHandler()
    executor = ScannerExecutor(registry=registry, indicators_registry={},
                               output_handler=output, db=None)

    class FakeOrmCandle:
        def __init__(self):
            self.timestamp = datetime(2024, 1, 1)
            self.open = "100.00"
            self.high = "102.00"
            self.low = "99.00"
            self.close = "101.00"
            self.volume = "1000000"

    orm_candles = [FakeOrmCandle()]
    candles = executor._to_candles(orm_candles)
    assert len(candles) == 1
    assert isinstance(candles[0].close, float)
    assert isinstance(candles[0].volume, int)
```

- [x] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_scanners.py -k "executor" -v
```

Expected output: `FAILED — ScannerExecutor not defined`

- [x] **Step 3: Implement ScannerExecutor with ORM→dataclass conversion and batch commits**

```python
# src/scanner/executor.py
import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from src.scanner.registry import ScannerRegistry
from src.scanner.context import ScanContext
from src.scanner.base import ScanResult
from src.scanner.indicators.cache import IndicatorCache
from src.data_provider.base import Candle
from src.output.base import OutputHandler

logger = logging.getLogger(__name__)


class ScannerExecutor:
    """Executes scanners for stocks with batch commits and ORM→dataclass conversion."""

    def __init__(
        self,
        registry: ScannerRegistry,
        indicators_registry: Dict,
        output_handler: OutputHandler,
        db: Optional[Session] = None,
    ):
        self.registry = registry
        self.indicators_registry = indicators_registry
        self.output_handler = output_handler
        self.db = db

    def _to_candles(self, orm_candles) -> List[Candle]:
        """Convert ORM DailyCandle objects to Candle dataclasses."""
        return [
            Candle(
                timestamp=c.timestamp,
                open=float(c.open),
                high=float(c.high),
                low=float(c.low),
                close=float(c.close),
                volume=int(c.volume),
            )
            for c in orm_candles
        ]

    def run_eod(
        self,
        stocks_with_candles: Dict[int, tuple],  # {stock_id: (symbol, List[Candle])}
    ) -> List[ScanResult]:
        """Run all scanners for each stock. Batch-commit all results per stock."""
        all_results = []

        for stock_id, (symbol, daily_candles) in stocks_with_candles.items():
            indicator_cache = IndicatorCache(self.indicators_registry)
            context = ScanContext(
                stock_id=stock_id,
                symbol=symbol,
                daily_candles=daily_candles,
                intraday_candles={},
                indicator_cache=indicator_cache,
            )

            stock_results: List[ScanResult] = []

            for scanner_name, scanner in self.registry.list().items():
                try:
                    results = scanner.scan(context)
                    for result in results:
                        stock_results.append(result)
                        all_results.append(result)
                        self.output_handler.emit_scan_result(result)
                except Exception:
                    logger.exception(f"{scanner_name} failed for {symbol}")

            # Batch-commit all results for this stock at once
            if stock_results:
                self._persist_results(stock_results)

        return all_results

    def _persist_results(self, results: List[ScanResult]) -> None:
        """Batch insert scanner results into the database."""
        if not results or not self.db:
            return
        from src.db.models import ScannerResult as ScannerResultModel
        self.db.add_all([
            ScannerResultModel(
                stock_id=r.stock_id,
                scanner_name=r.scanner_name,
                result_metadata=r.metadata,
                matched_at=r.matched_at,
            )
            for r in results
        ])
        self.db.commit()
```

- [x] **Step 4: Run tests**

```bash
pytest tests/unit/test_scanners.py -v
```

Expected output: all tests pass

- [x] **Step 5: Commit**

```bash
git add src/scanner/executor.py tests/unit/test_scanners.py
git commit -m "feat: add ScannerExecutor with ORM-to-dataclass conversion and batch commits"
```

---

### Task 17: Price action scanner (fixed exception logging)

**Files:**
- Create: `src/scanner/scanners/__init__.py`
- Create: `src/scanner/scanners/price_action.py`
- Create: `tests/unit/test_scanner_implementations.py`

- [x] **Step 1: Write failing test for price action scanner**

```python
# tests/unit/test_scanner_implementations.py
import pytest
from datetime import datetime
from src.scanner.scanners.price_action import PriceActionScanner
from src.scanner.scanners.momentum_scan import MomentumScanner
from src.scanner.scanners.volume_scan import VolumeScanner
from src.scanner.context import ScanContext
from src.scanner.indicators.cache import IndicatorCache
from src.scanner.indicators.moving_averages import SMA
from src.scanner.indicators.momentum import RSI
from src.data_provider.base import Candle


def make_scan_context(symbol="AAPL", closes=None, volumes=None):
    if closes is None:
        closes = [100 + i * 0.5 for i in range(220)]
    if volumes is None:
        volumes = [1_000_000] * len(closes)

    candles = [
        Candle(datetime(2024, 1, 1), c, c + 1, c - 1, c, v)
        for c, v in zip(closes, volumes)
    ]
    indicators = {"sma": SMA(), "rsi": RSI()}
    return ScanContext(
        stock_id=1, symbol=symbol,
        daily_candles=candles, intraday_candles={},
        indicator_cache=IndicatorCache(indicators),
    )


def test_price_action_scanner_returns_list():
    context = make_scan_context()
    scanner = PriceActionScanner()
    results = scanner.scan(context)
    assert isinstance(results, list)


def test_price_action_scanner_too_few_candles():
    context = make_scan_context(closes=[100.0] * 10)
    scanner = PriceActionScanner()
    results = scanner.scan(context)
    assert results == []


def test_momentum_scanner_returns_list():
    context = make_scan_context()
    scanner = MomentumScanner()
    results = scanner.scan(context)
    assert isinstance(results, list)


def test_momentum_scanner_too_few_candles():
    context = make_scan_context(closes=[100.0] * 10)
    scanner = MomentumScanner()
    results = scanner.scan(context)
    assert results == []


def test_volume_scanner_detects_spike():
    # 20 days at low volume, then 1 day at 3x volume
    base_vol = 1_000_000
    closes = [100.0] * 21
    volumes = [base_vol] * 20 + [base_vol * 3]
    context = make_scan_context(closes=closes, volumes=volumes)
    scanner = VolumeScanner()
    results = scanner.scan(context)
    assert len(results) == 1
    assert results[0].metadata["ratio"] == 3.0


def test_volume_scanner_no_spike():
    closes = [100.0] * 21
    volumes = [1_000_000] * 21
    context = make_scan_context(closes=closes, volumes=volumes)
    scanner = VolumeScanner()
    results = scanner.scan(context)
    assert results == []


def test_volume_scanner_too_few_candles():
    context = make_scan_context(closes=[100.0] * 10)
    scanner = VolumeScanner()
    results = scanner.scan(context)
    assert results == []
```

- [x] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_scanner_implementations.py::test_price_action_scanner_returns_list -v
```

Expected output: `FAILED — PriceActionScanner not defined`

- [x] **Step 3: Implement price_action.py**

```python
# src/scanner/scanners/price_action.py
import logging
import numpy as np
from typing import List
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext

logger = logging.getLogger(__name__)


class PriceActionScanner(Scanner):
    """Scan for price action breakouts and bounces above/at SMA50/SMA200."""

    def scan(self, context: ScanContext) -> List[ScanResult]:
        matches = []

        if len(context.daily_candles) < 200:
            return matches

        try:
            sma50 = context.get_indicator("sma", period=50)
            sma200 = context.get_indicator("sma", period=200)

            latest_close = float(context.daily_candles[-1].close)
            latest_high = float(context.daily_candles[-1].high)
            latest_low = float(context.daily_candles[-1].low)

            if len(sma50) > 0 and len(sma200) > 0 and latest_close > float(sma50[-1]) and float(sma50[-1]) > float(sma200[-1]):
                support_level = float(sma50[-1])
                if latest_low <= support_level <= latest_high:
                    matches.append(ScanResult(
                        stock_id=context.stock_id,
                        scanner_name="price_action",
                        metadata={
                            "reason": "bounce_off_support",
                            "support_level": support_level,
                            "current_price": latest_close,
                        },
                    ))
        except Exception:
            logger.exception(f"PriceActionScanner failed for {context.symbol}")

        return matches
```

- [x] **Step 4: Commit (partial — momentum and volume follow)**

```bash
git add src/scanner/scanners/price_action.py
git commit -m "feat: implement price action scanner with proper exception logging"
```

---

### Task 18: Momentum scanner (fixed exception logging)

**Files:**
- Create: `src/scanner/scanners/momentum_scan.py`

- [x] **Step 1: Run momentum scanner tests to verify they fail**

```bash
pytest tests/unit/test_scanner_implementations.py::test_momentum_scanner_returns_list -v
```

Expected output: `FAILED — MomentumScanner not defined`

- [x] **Step 2: Implement momentum_scan.py**

```python
# src/scanner/scanners/momentum_scan.py
import logging
from typing import List
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext

logger = logging.getLogger(__name__)


class MomentumScanner(Scanner):
    """Scan for RSI oversold/overbought conditions."""

    def scan(self, context: ScanContext) -> List[ScanResult]:
        matches = []

        if len(context.daily_candles) < 50:
            return matches

        try:
            rsi = context.get_indicator("rsi", period=14)

            if len(rsi) == 0:
                return matches

            latest_rsi = float(rsi[-1])

            if latest_rsi < 30:
                matches.append(ScanResult(
                    stock_id=context.stock_id,
                    scanner_name="momentum",
                    metadata={"reason": "oversold", "rsi": latest_rsi},
                ))
            elif latest_rsi > 70:
                matches.append(ScanResult(
                    stock_id=context.stock_id,
                    scanner_name="momentum",
                    metadata={"reason": "overbought", "rsi": latest_rsi},
                ))
        except Exception:
            logger.exception(f"MomentumScanner failed for {context.symbol}")

        return matches
```

- [x] **Step 3: Run tests**

```bash
pytest tests/unit/test_scanner_implementations.py -k "momentum" -v
```

Expected output: `2 passed`

- [x] **Step 4: Commit**

```bash
git add src/scanner/scanners/momentum_scan.py
git commit -m "feat: implement momentum scanner with proper exception logging"
```

---

### Task 19: Volume scanner (new)

**Files:**
- Create: `src/scanner/scanners/volume_scan.py`
- Modify: `src/scanner/scanners/__init__.py`

- [x] **Step 1: Run volume scanner tests to verify they fail**

```bash
pytest tests/unit/test_scanner_implementations.py::test_volume_scanner_detects_spike -v
```

Expected output: `FAILED — VolumeScanner not defined`

- [x] **Step 2: Implement volume_scan.py**

```python
# src/scanner/scanners/volume_scan.py
import logging
import numpy as np
from typing import List
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext

logger = logging.getLogger(__name__)


class VolumeScanner(Scanner):
    """Scan for volume spikes relative to 20-day average."""

    def scan(self, context: ScanContext) -> List[ScanResult]:
        matches = []

        if len(context.daily_candles) < 21:
            return matches

        try:
            closes = np.array([float(c.close) for c in context.daily_candles])
            volumes = np.array([float(c.volume) for c in context.daily_candles])

            avg_volume = np.mean(volumes[-21:-1])  # Prior 20 days, not today
            latest_volume = volumes[-1]

            if latest_volume > 2.0 * avg_volume:
                direction = "up" if closes[-1] > closes[-2] else "down"
                matches.append(ScanResult(
                    stock_id=context.stock_id,
                    scanner_name="volume",
                    metadata={
                        "reason": f"volume_spike_{direction}",
                        "volume": float(latest_volume),
                        "avg_volume_20d": float(avg_volume),
                        "ratio": round(float(latest_volume / avg_volume), 2),
                    },
                ))
        except Exception:
            logger.exception(f"VolumeScanner failed for {context.symbol}")

        return matches
```

- [x] **Step 3: Create scanners/__init__.py**

```python
# src/scanner/scanners/__init__.py
from src.scanner.scanners.price_action import PriceActionScanner
from src.scanner.scanners.momentum_scan import MomentumScanner
from src.scanner.scanners.volume_scan import VolumeScanner

__all__ = ["PriceActionScanner", "MomentumScanner", "VolumeScanner"]
```

- [x] **Step 4: Run all scanner implementation tests**

```bash
pytest tests/unit/test_scanner_implementations.py -v
```

Expected output: `7 passed`

- [x] **Step 5: Commit**

```bash
git add src/scanner/scanners/ tests/unit/test_scanner_implementations.py
git commit -m "feat: add VolumeScanner and scanners package"
```

---

## Phase 6: Output Handlers

### Task 20: Output handlers (Alert dataclass, CLIOutputHandler, LogFileOutputHandler, CompositeOutputHandler with logging)

**Files:**
- Create: `src/output/__init__.py`
- Create: `src/output/base.py`
- Create: `src/output/cli.py`
- Create: `src/output/logger.py`
- Create: `src/output/composite.py`
- Create: `tests/unit/test_output_handlers.py`

- [x] **Step 1: Write failing tests for output handlers**

```python
# tests/unit/test_output_handlers.py
import pytest
import logging
from datetime import datetime
from unittest.mock import MagicMock
from src.scanner.base import ScanResult
from src.output.base import OutputHandler, Alert
from src.output.cli import CLIOutputHandler
from src.output.composite import CompositeOutputHandler
from src.data_provider.base import Quote


def make_quote():
    return Quote(
        timestamp=datetime.now(),
        bid=100.0, ask=100.5, bid_size=100, ask_size=100,
        last=100.2, open=99.5, high=101, low=99, close=100,
        volume=1000000, change=0.5, change_pct=0.5,
        week_52_high=120, week_52_low=80, status="active",
    )


def test_alert_dataclass():
    alert = Alert(ticker="AAPL", reason="test", quote=make_quote())
    assert alert.ticker == "AAPL"
    assert alert.timestamp is not None


def test_cli_handler_emit_does_not_raise(capsys):
    handler = CLIOutputHandler()
    result = ScanResult(stock_id=1, scanner_name="test", metadata={"key": "val"})
    handler.emit_scan_result(result)
    captured = capsys.readouterr()
    assert "test" in captured.out


def test_cli_handler_emit_alert(capsys):
    handler = CLIOutputHandler()
    alert = Alert(ticker="AAPL", reason="target_reached", quote=make_quote())
    handler.emit_alert(alert)
    captured = capsys.readouterr()
    assert "AAPL" in captured.out


def test_composite_handler_delegates_to_all():
    h1, h2 = MagicMock(), MagicMock()
    h1.emit_scan_result = MagicMock()
    h2.emit_scan_result = MagicMock()
    composite = CompositeOutputHandler([h1, h2])
    result = ScanResult(stock_id=1, scanner_name="test", metadata={})
    composite.emit_scan_result(result)
    h1.emit_scan_result.assert_called_once_with(result)
    h2.emit_scan_result.assert_called_once_with(result)


def test_composite_handler_logs_exception_not_silently_swallows(caplog):
    failing = MagicMock()
    failing.emit_scan_result.side_effect = RuntimeError("handler crashed")
    composite = CompositeOutputHandler([failing])
    result = ScanResult(stock_id=1, scanner_name="test", metadata={})
    with caplog.at_level(logging.ERROR):
        composite.emit_scan_result(result)
    assert "handler crashed" in caplog.text or "failed" in caplog.text.lower()
```

- [x] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_output_handlers.py::test_alert_dataclass -v
```

Expected output: `FAILED — Alert not defined`

- [x] **Step 3: Implement output/base.py — imports ScanResult from scanner.base**

```python
# src/output/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# ScanResult lives in scanner.base — single source of truth
from src.scanner.base import ScanResult  # noqa: F401 (re-export for convenience)


@dataclass
class Alert:
    """Real-time alert."""
    ticker: str
    reason: str
    quote: object  # Quote dataclass — avoid circular import
    timestamp: Optional[datetime] = field(default=None)

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class OutputHandler(ABC):
    """Abstraction for alert/result destinations."""

    @abstractmethod
    def emit_scan_result(self, result: ScanResult) -> None:
        pass

    @abstractmethod
    def emit_alert(self, alert: Alert) -> None:
        pass
```

- [x] **Step 4: Implement cli.py**

```python
# src/output/cli.py
from src.scanner.base import ScanResult
from src.output.base import OutputHandler, Alert


class CLIOutputHandler(OutputHandler):
    """Print scan results and alerts to stdout."""

    def emit_scan_result(self, result: ScanResult) -> None:
        print(f"[{result.scanner_name}] stock_id={result.stock_id} metadata={result.metadata}")

    def emit_alert(self, alert: Alert) -> None:
        print(f"ALERT: {alert.ticker} {alert.reason} @ ${alert.quote.last}")
```

- [x] **Step 5: Implement logger.py**

```python
# src/output/logger.py
import logging
import os
from src.scanner.base import ScanResult
from src.output.base import OutputHandler, Alert


class LogFileOutputHandler(OutputHandler):
    """Write scan results and alerts to a log file."""

    def __init__(self, log_file: str = "logs/market_data.log", log_level: str = "INFO"):
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        self.logger = logging.getLogger("market_data.output")
        self.logger.handlers.clear()
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        self.logger.addHandler(handler)
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))

    def emit_scan_result(self, result: ScanResult) -> None:
        self.logger.info(
            f"SCAN: {result.scanner_name} stock_id={result.stock_id} metadata={result.metadata}"
        )

    def emit_alert(self, alert: Alert) -> None:
        self.logger.warning(f"ALERT: {alert.ticker} {alert.reason} price=${alert.quote.last}")
```

- [x] **Step 6: Implement composite.py with exception logging (not silent swallow)**

```python
# src/output/composite.py
import logging
from typing import List
from src.scanner.base import ScanResult
from src.output.base import OutputHandler, Alert

logger = logging.getLogger(__name__)


class CompositeOutputHandler(OutputHandler):
    """Fan-out to multiple handlers; logs exceptions instead of silently swallowing them."""

    def __init__(self, handlers: List[OutputHandler]):
        self.handlers = handlers

    def emit_scan_result(self, result: ScanResult) -> None:
        for handler in self.handlers:
            try:
                handler.emit_scan_result(result)
            except Exception:
                logger.exception(f"{handler.__class__.__name__} failed on emit_scan_result")

    def emit_alert(self, alert: Alert) -> None:
        for handler in self.handlers:
            try:
                handler.emit_alert(alert)
            except Exception:
                logger.exception(f"{handler.__class__.__name__} failed on emit_alert")
```

- [x] **Step 7: Create __init__.py**

```python
# src/output/__init__.py
from src.output.base import OutputHandler, Alert
from src.output.cli import CLIOutputHandler
from src.output.logger import LogFileOutputHandler
from src.output.composite import CompositeOutputHandler
from src.scanner.base import ScanResult  # re-export for convenience

__all__ = [
    "OutputHandler", "ScanResult", "Alert",
    "CLIOutputHandler", "LogFileOutputHandler", "CompositeOutputHandler",
]
```

- [x] **Step 8: Run tests**

```bash
pytest tests/unit/test_output_handlers.py -v
```

Expected output: `5 passed`

- [x] **Step 9: Commit**

```bash
git add src/output/ tests/unit/test_output_handlers.py
git commit -m "feat: add output handlers; ScanResult imported from scanner.base (single source)"
```

---

## Phase 7: Data Fetching

### Task 21: DataFetcher (bulk upsert, sync_daily, sync_intraday, sync_news, sync_earnings, rate limiting)

**Files:**
- Create: `src/data_fetcher/__init__.py`
- Create: `src/data_fetcher/fetcher.py`
- Create: `tests/integration/test_fetcher_db.py`

- [x] **Step 1: Write failing integration tests for DataFetcher**

```python
# tests/integration/test_fetcher_db.py
import pytest
from unittest.mock import Mock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from src.data_fetcher.fetcher import DataFetcher
from src.db.models import Stock, DailyCandle, IntradayCandle, StockNews
from src.data_provider.base import DataProvider, Candle, NewsArticle


def test_fetcher_bulk_upsert_daily_candles(db_session: Session):
    stock = Stock(symbol="AAPL", name="Apple")
    db_session.add(stock)
    db_session.commit()

    mock_provider = Mock(spec=DataProvider)
    mock_provider.get_daily_candles.return_value = [
        Candle(datetime(2024, 1, i + 1), 150.0, 152.0, 149.0, 151.0, 1000000)
        for i in range(5)
    ]

    fetcher = DataFetcher(provider=mock_provider, db=db_session, rate_limit_delay=0)
    fetcher.sync_daily(symbols=["AAPL"])

    aapl = db_session.query(Stock).filter_by(symbol="AAPL").first()
    assert len(aapl.daily_candles) == 5


def test_fetcher_daily_no_duplicate_on_resync(db_session: Session):
    stock = Stock(symbol="GOOGL", name="Google")
    db_session.add(stock)
    db_session.commit()

    mock_provider = Mock(spec=DataProvider)
    mock_provider.get_daily_candles.return_value = [
        Candle(datetime(2024, 1, 1), 150.0, 152.0, 149.0, 151.0, 1000000),
    ]

    fetcher = DataFetcher(provider=mock_provider, db=db_session, rate_limit_delay=0)
    fetcher.sync_daily(symbols=["GOOGL"])
    fetcher.sync_daily(symbols=["GOOGL"])  # second sync — same data

    googl = db_session.query(Stock).filter_by(symbol="GOOGL").first()
    assert len(googl.daily_candles) == 1  # no duplicate


def test_fetcher_sync_intraday(db_session: Session):
    stock = Stock(symbol="TSLA", name="Tesla")
    db_session.add(stock)
    db_session.commit()

    mock_provider = Mock(spec=DataProvider)
    mock_provider.get_intraday_candles.return_value = [
        Candle(datetime(2024, 1, 1, 9, 30), 100.0, 101.0, 99.0, 100.5, 50000),
        Candle(datetime(2024, 1, 1, 9, 35), 100.5, 102.0, 100.0, 101.0, 60000),
    ]

    fetcher = DataFetcher(provider=mock_provider, db=db_session, rate_limit_delay=0)
    fetcher.sync_intraday(symbols=["TSLA"], resolutions=["5m"], days_back=1)

    tsla = db_session.query(Stock).filter_by(symbol="TSLA").first()
    assert len(tsla.intraday_candles) == 2


def test_fetcher_sync_news(db_session: Session):
    stock = Stock(symbol="NVDA", name="Nvidia")
    db_session.add(stock)
    db_session.commit()

    mock_provider = Mock(spec=DataProvider)
    mock_provider.get_news.return_value = [
        NewsArticle(
            symbol="NVDA",
            headline="Nvidia releases new GPU",
            content="Details here",
            source="Reuters",
            publication_date=datetime(2024, 1, 1),
        )
    ]

    fetcher = DataFetcher(provider=mock_provider, db=db_session, rate_limit_delay=0)
    fetcher.sync_news(symbols=["NVDA"])

    nvda = db_session.query(Stock).filter_by(symbol="NVDA").first()
    assert len(nvda.news) == 1
    assert nvda.news[0].headline == "Nvidia releases new GPU"
```

- [x] **Step 2: Run test to verify it fails**

```bash
pytest tests/integration/test_fetcher_db.py::test_fetcher_bulk_upsert_daily_candles -v
```

Expected output: `FAILED — DataFetcher not defined`

- [x] **Step 3: Implement DataFetcher with bulk upsert and rate limiting**

```python
# src/data_fetcher/fetcher.py
import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.data_provider.base import DataProvider
from src.db.models import Stock, DailyCandle, IntradayCandle, EarningsCalendar, StockNews, RealtimeQuote

logger = logging.getLogger(__name__)


class DataFetcher:
    """Orchestrates all data syncing operations with bulk upsert and rate limiting."""

    def __init__(
        self,
        provider: DataProvider,
        db: Session,
        rate_limit_delay: float = 0.1,
    ):
        self.provider = provider
        self.db = db
        self.rate_limit_delay = rate_limit_delay

    # ------------------------------------------------------------------ #
    #  Bulk upsert helpers                                                 #
    # ------------------------------------------------------------------ #

    def _bulk_upsert_daily_candles(self, stock_id: int, candles) -> int:
        if not candles:
            return 0
        rows = [
            {
                "stock_id": stock_id,
                "timestamp": c.timestamp,
                "open": c.open, "high": c.high, "low": c.low,
                "close": c.close, "volume": c.volume,
            }
            for c in candles
        ]
        stmt = pg_insert(DailyCandle).values(rows).on_conflict_do_nothing(
            index_elements=["stock_id", "timestamp"]
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount

    def _bulk_upsert_intraday_candles(self, stock_id: int, resolution: str, candles) -> int:
        if not candles:
            return 0
        rows = [
            {
                "stock_id": stock_id,
                "resolution": resolution,
                "timestamp": c.timestamp,
                "open": c.open, "high": c.high, "low": c.low,
                "close": c.close, "volume": c.volume,
            }
            for c in candles
        ]
        stmt = pg_insert(IntradayCandle).values(rows).on_conflict_do_nothing(
            index_elements=["stock_id", "resolution", "timestamp"]
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount

    # ------------------------------------------------------------------ #
    #  Public sync methods                                                 #
    # ------------------------------------------------------------------ #

    def sync_daily(
        self,
        symbols: Optional[List[str]] = None,
        days_back: int = 365,
    ) -> None:
        """Sync daily candles for all (or specified) stocks."""
        if symbols is None:
            symbols = [s.symbol for s in self.db.query(Stock).all()]

        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days_back)

        for symbol in symbols:
            stock = self.db.query(Stock).filter_by(symbol=symbol).first()
            if not stock:
                logger.warning(f"Stock {symbol} not found in DB — skipping")
                continue
            try:
                candles = self.provider.get_daily_candles(
                    symbol=symbol, from_date=from_date, to_date=to_date
                )
                inserted = self._bulk_upsert_daily_candles(stock.id, candles)
                logger.info(f"sync_daily {symbol}: {inserted} new rows")
                time.sleep(self.rate_limit_delay)
            except Exception as e:
                logger.error(f"Failed to sync daily {symbol}: {e}")
                self.db.rollback()

    def sync_intraday(
        self,
        symbols: Optional[List[str]] = None,
        resolutions: Optional[List[str]] = None,
        days_back: int = 7,
    ) -> None:
        """Sync intraday candles for 5m, 15m, 1h resolutions."""
        if resolutions is None:
            resolutions = ["5m", "15m", "1h"]
        if symbols is None:
            symbols = [s.symbol for s in self.db.query(Stock).all()]

        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days_back)

        for symbol in symbols:
            stock = self.db.query(Stock).filter_by(symbol=symbol).first()
            if not stock:
                continue
            for resolution in resolutions:
                try:
                    candles = self.provider.get_intraday_candles(
                        symbol=symbol, resolution=resolution,
                        from_date=from_date, to_date=to_date,
                    )
                    inserted = self._bulk_upsert_intraday_candles(stock.id, resolution, candles)
                    logger.info(f"sync_intraday {symbol} {resolution}: {inserted} new rows")
                    time.sleep(self.rate_limit_delay)
                except Exception as e:
                    logger.error(f"Failed to sync intraday {symbol} {resolution}: {e}")
                    self.db.rollback()

    def sync_news(
        self,
        symbols: Optional[List[str]] = None,
        countback: int = 50,
    ) -> None:
        """Sync news articles for all stocks."""
        if symbols is None:
            symbols = [s.symbol for s in self.db.query(Stock).all()]

        for symbol in symbols:
            stock = self.db.query(Stock).filter_by(symbol=symbol).first()
            if not stock:
                continue
            try:
                articles = self.provider.get_news(symbol=symbol, countback=countback)
                for article in articles:
                    stmt = pg_insert(StockNews).values(
                        stock_id=stock.id,
                        headline=article.headline,
                        content=article.content,
                        source=article.source,
                        publication_date=article.publication_date,
                    ).on_conflict_do_nothing()
                    self.db.execute(stmt)
                self.db.commit()
                time.sleep(self.rate_limit_delay)
            except Exception as e:
                logger.error(f"Failed to sync news {symbol}: {e}")
                self.db.rollback()

    def sync_earnings(self, symbols: Optional[List[str]] = None) -> None:
        """Sync earnings calendar."""
        if symbols is None:
            symbols = [s.symbol for s in self.db.query(Stock).all()]

        for symbol in symbols:
            stock = self.db.query(Stock).filter_by(symbol=symbol).first()
            if not stock:
                continue
            try:
                earnings = self.provider.get_earnings_history(symbol=symbol)
                rows = [
                    {
                        "stock_id": stock.id,
                        "fiscal_year": e.fiscal_year,
                        "fiscal_quarter": e.fiscal_quarter,
                        "earnings_date": e.earnings_date,
                        "report_date": e.report_date,
                        "report_time": e.report_time,
                        "currency": e.currency,
                        "reported_eps": e.reported_eps,
                        "estimated_eps": e.estimated_eps,
                    }
                    for e in earnings
                ]
                if rows:
                    stmt = pg_insert(EarningsCalendar).values(rows).on_conflict_do_nothing(
                        index_elements=["stock_id", "earnings_date"]
                    )
                    self.db.execute(stmt)
                    self.db.commit()
                time.sleep(self.rate_limit_delay)
            except Exception as e:
                logger.error(f"Failed to sync earnings {symbol}: {e}")
                self.db.rollback()

    def cleanup_old_intraday(self, days_retention: int = 7) -> None:
        """Delete intraday candles older than retention period."""
        cutoff = datetime.utcnow() - timedelta(days=days_retention)
        deleted = self.db.query(IntradayCandle).filter(IntradayCandle.created_at < cutoff).delete()
        self.db.commit()
        logger.info(f"Deleted {deleted} old intraday candles")

    def cleanup_old_quotes(self, days_retention: int = 7) -> None:
        """Delete realtime quotes older than retention period."""
        cutoff = datetime.utcnow() - timedelta(days=days_retention)
        deleted = self.db.query(RealtimeQuote).filter(RealtimeQuote.created_at < cutoff).delete()
        self.db.commit()
        logger.info(f"Deleted {deleted} old realtime quotes")
```

- [x] **Step 4: Create __init__.py**

```python
# src/data_fetcher/__init__.py
from src.data_fetcher.fetcher import DataFetcher

__all__ = ["DataFetcher"]
```

- [x] **Step 5: Run integration tests**

```bash
pytest tests/integration/test_fetcher_db.py -v
```

Expected output: `4 passed`

- [x] **Step 6: Commit**

```bash
git add src/data_fetcher/ tests/integration/test_fetcher_db.py
git commit -m "feat: implement DataFetcher with bulk upsert, sync_intraday, sync_news, rate limiting"
```

---

### Task 22: APScheduler (create_eod_scheduler)

**Files:**
- Create: `src/data_fetcher/scheduler.py`

- [x] **Step 1: Write failing test for scheduler**

```python
# tests/unit/test_scheduler.py
import pytest
from unittest.mock import MagicMock
from src.data_fetcher.scheduler import create_eod_scheduler


def test_create_eod_scheduler_returns_scheduler():
    callback = MagicMock()
    scheduler = create_eod_scheduler(callback)
    assert scheduler is not None


def test_scheduler_has_eod_job():
    callback = MagicMock()
    scheduler = create_eod_scheduler(callback)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "eod_pipeline"


def test_scheduler_job_name():
    callback = MagicMock()
    scheduler = create_eod_scheduler(callback)
    assert scheduler.get_jobs()[0].name == "EOD Scanner Pipeline"
```

- [x] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_scheduler.py::test_create_eod_scheduler_returns_scheduler -v
```

Expected output: `FAILED — create_eod_scheduler not defined`

- [x] **Step 3: Implement scheduler.py**

```python
# src/data_fetcher/scheduler.py
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


def create_eod_scheduler(eod_callback) -> BlockingScheduler:
    """Schedule EOD pipeline at 4:15 PM ET Monday–Friday."""
    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        eod_callback,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=16,
            minute=15,
            timezone="America/New_York",
        ),
        id="eod_pipeline",
        name="EOD Scanner Pipeline",
        misfire_grace_time=300,
        coalesce=True,
    )
    return scheduler
```

- [x] **Step 4: Run tests**

```bash
pytest tests/unit/test_scheduler.py -v
```

Expected output: `3 passed`

- [x] **Step 5: Commit**

```bash
git add src/data_fetcher/scheduler.py tests/unit/test_scheduler.py
git commit -m "feat: add APScheduler EOD cron (4:15 PM ET Mon-Fri)"
```

---

## Phase 8: Realtime Monitor

### Task 23: Realtime monitor (fixed db.query(Stock), batch commits, alert rules)

**Files:**
- Create: `src/realtime_monitor/__init__.py`
- Create: `src/realtime_monitor/rules.py`
- Create: `src/realtime_monitor/alert_engine.py`
- Create: `src/realtime_monitor/monitor.py`
- Create: `tests/unit/test_alert_rules.py`

- [x] **Step 1: Write failing tests for alert rules**

```python
# tests/unit/test_alert_rules.py
import pytest
from datetime import datetime
from src.realtime_monitor.rules import PriceTargetRule, PercentageGainRule, PercentageLossRule
from src.data_provider.base import Quote


def make_quote(last: float):
    return Quote(
        timestamp=datetime.now(),
        bid=last - 0.5, ask=last + 0.5, bid_size=100, ask_size=100,
        last=last, open=100, high=last + 1, low=last - 1, close=last,
        volume=1000000, change=0, change_pct=0,
        week_52_high=150, week_52_low=80, status="active",
    )


def test_price_target_rule_triggers():
    rule = PriceTargetRule(target_price=105.0)
    assert rule.should_alert(make_quote(105.2)) is True


def test_price_target_rule_no_trigger():
    rule = PriceTargetRule(target_price=110.0)
    assert rule.should_alert(make_quote(100.2)) is False


def test_percentage_gain_rule_triggers():
    rule = PercentageGainRule(entry_price=100.0, gain_pct=5.0)
    assert rule.should_alert(make_quote(106.0)) is True


def test_percentage_gain_rule_no_trigger():
    rule = PercentageGainRule(entry_price=100.0, gain_pct=5.0)
    assert rule.should_alert(make_quote(103.0)) is False


def test_percentage_loss_rule_triggers():
    rule = PercentageLossRule(entry_price=100.0, loss_pct=5.0)
    assert rule.should_alert(make_quote(94.0)) is True
```

- [x] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_alert_rules.py::test_price_target_rule_triggers -v
```

Expected output: `FAILED — PriceTargetRule not defined`

- [x] **Step 3: Implement rules.py**

```python
# src/realtime_monitor/rules.py
from abc import ABC, abstractmethod
from src.data_provider.base import Quote


class AlertRule(ABC):
    @abstractmethod
    def should_alert(self, quote: Quote) -> bool:
        pass


class PriceTargetRule(AlertRule):
    """Alert when price reaches or exceeds target."""

    def __init__(self, target_price: float):
        self.target_price = target_price

    def should_alert(self, quote: Quote) -> bool:
        return quote.last >= self.target_price


class PercentageGainRule(AlertRule):
    """Alert when price gains >= gain_pct% from entry."""

    def __init__(self, entry_price: float, gain_pct: float = 5.0):
        self.entry_price = entry_price
        self.gain_pct = gain_pct

    def should_alert(self, quote: Quote) -> bool:
        gain = ((quote.last - self.entry_price) / self.entry_price) * 100
        return gain >= self.gain_pct


class PercentageLossRule(AlertRule):
    """Alert when price drops >= loss_pct% from entry."""

    def __init__(self, entry_price: float, loss_pct: float = 5.0):
        self.entry_price = entry_price
        self.loss_pct = loss_pct

    def should_alert(self, quote: Quote) -> bool:
        loss = ((self.entry_price - quote.last) / self.entry_price) * 100
        return loss >= self.loss_pct
```

- [x] **Step 4: Implement alert_engine.py**

```python
# src/realtime_monitor/alert_engine.py
import logging
from typing import Dict, List
from src.realtime_monitor.rules import AlertRule
from src.data_provider.base import Quote

logger = logging.getLogger(__name__)


class AlertEngine:
    """Manages alert rules for tracked tickers."""

    def __init__(self):
        self.rules: Dict[str, List[AlertRule]] = {}

    def add_rule(self, ticker: str, rule: AlertRule) -> None:
        self.rules.setdefault(ticker, []).append(rule)

    def should_alert(self, ticker: str, quote: Quote) -> bool:
        return any(rule.should_alert(quote) for rule in self.rules.get(ticker, []))

    def clear_rules(self, ticker: str) -> None:
        self.rules.pop(ticker, None)
```

- [x] **Step 5: Implement monitor.py with fixed db.query(Stock) and batch commits**

```python
# src/realtime_monitor/monitor.py
import logging
import time
from typing import Set
from datetime import datetime
from sqlalchemy.orm import Session

from src.data_provider.base import DataProvider
from src.db.models import Stock, ScannerResult, RealtimeQuote as RealtimeQuoteModel
from src.realtime_monitor.alert_engine import AlertEngine
from src.output.base import OutputHandler, Alert

logger = logging.getLogger(__name__)


class RealtimeMonitor:
    """Monitors matched tickers from EOD scanner, stores quotes, fires alerts."""

    def __init__(
        self,
        provider: DataProvider,
        db: Session,
        output_handler: OutputHandler,
        alert_engine: AlertEngine,
    ):
        self.provider = provider
        self.db = db
        self.output_handler = output_handler
        self.alert_engine = alert_engine
        self.watched_tickers: Set[str] = set()

    def load_scanner_results(self, scanner_name: str) -> None:
        """Load tickers matched by today's scanner."""
        today = datetime.utcnow().date()
        results = self.db.query(ScannerResult).filter(
            ScannerResult.scanner_name == scanner_name,
            ScannerResult.matched_at >= today,
        ).all()
        self.watched_tickers = {r.stock.symbol for r in results}
        logger.info(f"Loaded {len(self.watched_tickers)} tickers from {scanner_name}")

    def poll_quotes(self, interval_seconds: int = 5, max_iterations: int = None) -> None:
        """Poll realtime quotes for watched tickers; batch all inserts per cycle."""
        iteration = 0

        while True:
            if max_iterations is not None and iteration >= max_iterations:
                break
            iteration += 1

            records_to_add = []

            for ticker in list(self.watched_tickers):
                try:
                    quote = self.provider.get_realtime_quote(ticker)
                    # db.query(Stock) — correct ORM model, not a string literal
                    stock = self.db.query(Stock).filter_by(symbol=ticker).first()
                    if stock:
                        records_to_add.append(RealtimeQuoteModel(
                            stock_id=stock.id,
                            bid=quote.bid, ask=quote.ask,
                            bid_size=quote.bid_size, ask_size=quote.ask_size,
                            last=quote.last, open=quote.open, high=quote.high,
                            low=quote.low, close=quote.close, volume=quote.volume,
                            change=quote.change, change_pct=quote.change_pct,
                            week_52_high=quote.week_52_high, week_52_low=quote.week_52_low,
                            status=quote.status, timestamp=quote.timestamp,
                        ))
                    if self.alert_engine.should_alert(ticker, quote):
                        self.output_handler.emit_alert(
                            Alert(ticker=ticker, reason="target_reached", quote=quote)
                        )
                except Exception as e:
                    logger.error(f"Error polling {ticker}: {e}")

            # Batch commit all records from this poll cycle
            if records_to_add:
                self.db.add_all(records_to_add)
                self.db.commit()

            time.sleep(interval_seconds)
```

- [x] **Step 6: Create __init__.py**

```python
# src/realtime_monitor/__init__.py
from src.realtime_monitor.alert_engine import AlertEngine
from src.realtime_monitor.monitor import RealtimeMonitor

__all__ = ["AlertEngine", "RealtimeMonitor"]
```

- [x] **Step 7: Run tests**

```bash
pytest tests/unit/test_alert_rules.py -v
```

Expected output: `5 passed`

- [x] **Step 8: Commit**

```bash
git add src/realtime_monitor/ tests/unit/test_alert_rules.py
git commit -m "feat: add realtime monitor (batch commits, correct db.query) and alert rules"
```

---

## Phase 9: Main Entry Point

### Task 24: Main entry point (lazy DB init, eod, monitor, schedule, seed-universe, init-db commands)

**Files:**
- Create: `src/main.py`

- [x] **Step 1: Write failing test for main CLI**

```python
# tests/unit/test_main.py
import pytest
from click.testing import CliRunner
from src.main import app


def test_cli_app_exists():
    assert app is not None


def test_cli_help_runs():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "eod" in result.output or "Usage" in result.output


def test_cli_does_not_init_db_at_import():
    """Importing src.main must not trigger DB connection."""
    import importlib
    # Should not raise even without DATABASE_URL set
    try:
        importlib.import_module("src.main")
    except Exception as e:
        pytest.fail(f"Importing src.main raised unexpectedly: {e}")
```

- [x] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_main.py::test_cli_app_exists -v
```

Expected output: `FAILED — app not defined`

- [x] **Step 3: Implement main.py with lazy DB init and all commands**

```python
# src/main.py
import csv
import logging

import click

logger = logging.getLogger(__name__)


@click.group()
def app():
    """Market Data Infrastructure CLI."""
    pass


def _get_db_session():
    """Lazy DB session factory — called at runtime, never at import time."""
    from src.config import get_config
    from src.db.connection import get_engine, init_db
    from sqlalchemy.orm import sessionmaker

    cfg = get_config()
    engine = get_engine(cfg.DATABASE_URL)
    init_db(engine)
    return sessionmaker(bind=engine)()


@app.command()
@click.option("--symbols", multiple=True, help="Stock symbols to sync (default: all)")
def eod(symbols):
    """Run EOD scanner pipeline."""
    from src.config import get_config
    from src.data_provider.marketdata_app import MarketDataAppProvider
    from src.data_fetcher.fetcher import DataFetcher
    from src.scanner.registry import ScannerRegistry
    from src.scanner.executor import ScannerExecutor
    from src.scanner.indicators.moving_averages import SMA, EMA, WMA
    from src.scanner.indicators.momentum import RSI, MACD
    from src.scanner.indicators.volatility import BollingerBands, ATR
    from src.scanner.indicators.support_resistance import SupportResistance
    from src.scanner.indicators.patterns.breakouts import BreakoutDetector
    from src.scanner.scanners import PriceActionScanner, MomentumScanner, VolumeScanner
    from src.output.cli import CLIOutputHandler
    from src.output.logger import LogFileOutputHandler
    from src.output.composite import CompositeOutputHandler
    from src.db.models import Stock
    from sqlalchemy.orm import joinedload

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info("Starting EOD pipeline...")

    db = _get_db_session()
    try:
        provider = MarketDataAppProvider(
            api_token=cfg.MARKETDATA_API_TOKEN,
            max_retries=cfg.MAX_RETRIES,
            retry_backoff_base=cfg.RETRY_BACKOFF_BASE,
        )
        fetcher = DataFetcher(provider=provider, db=db, rate_limit_delay=cfg.API_RATE_LIMIT_DELAY)

        logger.info("Fetching daily candles...")
        fetcher.sync_daily(symbols=list(symbols) if symbols else None)

        logger.info("Fetching earnings...")
        fetcher.sync_earnings(symbols=list(symbols) if symbols else None)

        logger.info("Cleaning up old data...")
        fetcher.cleanup_old_intraday()
        fetcher.cleanup_old_quotes()

        indicators = {
            "sma": SMA(), "ema": EMA(), "wma": WMA(),
            "rsi": RSI(), "macd": MACD(),
            "bollinger": BollingerBands(), "atr": ATR(),
            "support_resistance": SupportResistance(),
            "breakout": BreakoutDetector(),
        }

        scanner_registry = ScannerRegistry()
        scanner_registry.register("price_action", PriceActionScanner())
        scanner_registry.register("momentum", MomentumScanner())
        scanner_registry.register("volume", VolumeScanner())

        output = CompositeOutputHandler([
            CLIOutputHandler(),
            LogFileOutputHandler(log_file=cfg.LOG_FILE, log_level=cfg.LOG_LEVEL),
        ])

        # Load stocks with candles via joinedload to avoid N+1
        stocks = db.query(Stock).options(joinedload(Stock.daily_candles)).all()
        executor = ScannerExecutor(
            registry=scanner_registry,
            indicators_registry=indicators,
            output_handler=output,
            db=db,
        )
        stocks_with_candles = {
            s.id: (s.symbol, executor._to_candles(sorted(s.daily_candles, key=lambda c: c.timestamp)))
            for s in stocks
            if s.daily_candles
        }

        results = executor.run_eod(stocks_with_candles)
        logger.info(f"EOD complete. Found {len(results)} matches.")
        click.echo(f"EOD pipeline complete. {len(results)} matches found.")

    except Exception as e:
        logger.error(f"EOD pipeline failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
    finally:
        db.close()


@app.command()
@click.option("--scanner", default="price_action", help="Scanner to monitor results from")
@click.option("--interval", default=5, type=int, help="Poll interval in seconds")
def monitor(scanner, interval):
    """Run realtime monitor for scanner matches."""
    from src.config import get_config
    from src.data_provider.marketdata_app import MarketDataAppProvider
    from src.output.cli import CLIOutputHandler
    from src.output.logger import LogFileOutputHandler
    from src.output.composite import CompositeOutputHandler
    from src.realtime_monitor.monitor import RealtimeMonitor
    from src.realtime_monitor.alert_engine import AlertEngine

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info(f"Starting realtime monitor for {scanner} scanner...")

    db = _get_db_session()
    try:
        provider = MarketDataAppProvider(
            api_token=cfg.MARKETDATA_API_TOKEN,
            max_retries=cfg.MAX_RETRIES,
            retry_backoff_base=cfg.RETRY_BACKOFF_BASE,
        )
        output = CompositeOutputHandler([
            CLIOutputHandler(),
            LogFileOutputHandler(log_file=cfg.LOG_FILE, log_level=cfg.LOG_LEVEL),
        ])
        alert_engine = AlertEngine()
        mon = RealtimeMonitor(
            provider=provider, db=db,
            output_handler=output, alert_engine=alert_engine,
        )
        mon.load_scanner_results(scanner)

        if not mon.watched_tickers:
            logger.warning(f"No matches found for {scanner}")
            click.echo(f"No matches found for scanner '{scanner}'.")
            return

        logger.info(f"Monitoring {len(mon.watched_tickers)} tickers")
        mon.poll_quotes(interval_seconds=interval)

    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")
        click.echo("Monitor stopped.")
    except Exception as e:
        logger.error(f"Monitor failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
    finally:
        db.close()


@app.command("init-db")
def init_db_cmd():
    """Initialize database schema."""
    from src.config import get_config
    from src.db.connection import get_engine, init_db

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info("Initializing database...")
    try:
        engine = get_engine(cfg.DATABASE_URL)
        init_db(engine)
        logger.info("Database initialized successfully")
        click.echo("Database initialized.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        click.echo(f"Error: {e}", err=True)


@app.command("seed-universe")
@click.option("--file", "universe_file", type=click.Path(exists=True),
              help="CSV with symbol,name,sector columns")
@click.option("--symbols", multiple=True, help="Stock symbols to add")
def seed_universe(universe_file, symbols):
    """Seed stock universe from CSV or symbol list."""
    from src.db.models import Stock

    db = _get_db_session()
    try:
        added = 0
        if universe_file:
            with open(universe_file) as f:
                for row in csv.DictReader(f):
                    sym = row["symbol"].strip().upper()
                    if not db.query(Stock).filter_by(symbol=sym).first():
                        db.add(Stock(
                            symbol=sym,
                            name=row.get("name", ""),
                            sector=row.get("sector", ""),
                        ))
                        added += 1
        for sym in symbols:
            sym = sym.strip().upper()
            if not db.query(Stock).filter_by(symbol=sym).first():
                db.add(Stock(symbol=sym))
                added += 1
        db.commit()
        total = db.query(Stock).count()
        click.echo(f"Added {added} stocks. Universe total: {total}")
    except Exception as e:
        logger.error(f"seed-universe failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
    finally:
        db.close()


@app.command("schedule")
def schedule_cmd():
    """Start the blocking APScheduler (runs EOD pipeline at 4:15 PM ET Mon-Fri)."""
    from src.data_fetcher.scheduler import create_eod_scheduler
    from src.config import get_config

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info("Starting APScheduler...")

    def run_eod():
        """Callback invoked by scheduler — imports lazily to avoid circular deps."""
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(eod, [])
        if result.exit_code != 0:
            logger.error(f"Scheduled EOD failed: {result.output}")

    scheduler = create_eod_scheduler(run_eod)
    try:
        click.echo("Scheduler started. Press Ctrl+C to stop.")
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
        click.echo("Scheduler stopped.")


if __name__ == "__main__":
    app()
```

- [x] **Step 4: Run tests**

```bash
pytest tests/unit/test_main.py -v
```

Expected output: `3 passed`

- [x] **Step 5: Commit**

```bash
git add src/main.py tests/unit/test_main.py
git commit -m "feat: add CLI entry point with lazy DB init, eod/monitor/schedule/seed-universe/init-db"
```

---

## Phase 10: Integration & Polish

### Task 25: Integration tests (testcontainers PostgreSQL, full E2E pipeline test)

**Files:**
- Create: `tests/integration/test_end_to_end.py`
- Create: `tests/fixtures/mock_data.py`

- [x] **Step 1: Create mock data fixtures**

```python
# tests/fixtures/mock_data.py
from datetime import datetime, timedelta
from src.data_provider.base import Candle, Quote, NewsArticle, Earning


def make_daily_candles(n: int = 250, base_price: float = 100.0) -> list:
    """Generate n daily candles with a gentle upward drift."""
    candles = []
    for i in range(n):
        close = base_price + i * 0.1 + (i % 7 - 3) * 0.5
        candles.append(Candle(
            timestamp=datetime(2024, 1, 1) + timedelta(days=i),
            open=close - 0.5,
            high=close + 1.0,
            low=close - 1.0,
            close=close,
            volume=1_000_000 + (i % 5) * 100_000,
        ))
    return candles


def make_quote(symbol: str = "AAPL", last: float = 150.0) -> Quote:
    return Quote(
        timestamp=datetime.utcnow(),
        bid=last - 0.05, ask=last + 0.05,
        bid_size=100, ask_size=100,
        last=last, open=last - 1, high=last + 2, low=last - 2, close=last,
        volume=5_000_000, change=1.0, change_pct=0.67,
        week_52_high=180.0, week_52_low=120.0, status="active",
    )
```

- [x] **Step 2: Write end-to-end integration test**

```python
# tests/integration/test_end_to_end.py
import pytest
from unittest.mock import Mock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from src.db.models import Stock, DailyCandle, ScannerResult
from src.data_provider.base import DataProvider, Candle
from src.data_fetcher.fetcher import DataFetcher
from src.scanner.registry import ScannerRegistry
from src.scanner.executor import ScannerExecutor
from src.scanner.indicators.moving_averages import SMA, EMA
from src.scanner.indicators.momentum import RSI
from src.scanner.indicators.volatility import BollingerBands, ATR
from src.scanner.indicators.support_resistance import SupportResistance
from src.scanner.scanners import PriceActionScanner, MomentumScanner, VolumeScanner
from src.output.cli import CLIOutputHandler
from tests.fixtures.mock_data import make_daily_candles


def test_full_pipeline_fetch_and_scan(db_session: Session):
    """Full pipeline: seed stock → mock fetch → bulk upsert → scan → verify DB results."""

    # 1. Seed stock universe
    stock = Stock(symbol="E2E", name="End-to-End Corp", sector="Test")
    db_session.add(stock)
    db_session.commit()

    # 2. Mock provider returns 250 daily candles
    mock_provider = Mock(spec=DataProvider)
    mock_provider.get_daily_candles.return_value = make_daily_candles(250)
    mock_provider.get_earnings_history.return_value = []

    # 3. Fetch and upsert
    fetcher = DataFetcher(provider=mock_provider, db=db_session, rate_limit_delay=0)
    fetcher.sync_daily(symbols=["E2E"])

    refreshed = db_session.query(Stock).filter_by(symbol="E2E").first()
    assert len(refreshed.daily_candles) == 250

    # 4. Build scanner machinery
    scanner_registry = ScannerRegistry()
    scanner_registry.register("price_action", PriceActionScanner())
    scanner_registry.register("momentum", MomentumScanner())
    scanner_registry.register("volume", VolumeScanner())

    indicators = {
        "sma": SMA(), "ema": EMA(), "rsi": RSI(),
        "bollinger": BollingerBands(), "atr": ATR(),
        "support_resistance": SupportResistance(),
    }
    output = CLIOutputHandler()
    executor = ScannerExecutor(
        registry=scanner_registry,
        indicators_registry=indicators,
        output_handler=output,
        db=db_session,
    )

    candles = executor._to_candles(
        sorted(refreshed.daily_candles, key=lambda c: c.timestamp)
    )
    stocks_with_candles = {refreshed.id: ("E2E", candles)}

    # 5. Run scanners
    results = executor.run_eod(stocks_with_candles)

    # 6. Verify pipeline ran to completion
    assert isinstance(results, list)
    stored = db_session.query(ScannerResult).filter_by(stock_id=refreshed.id).all()
    assert len(stored) == len(results)


def test_bulk_upsert_idempotent(db_session: Session):
    """Syncing same candles twice must not create duplicates."""
    stock = Stock(symbol="IDEM", name="Idempotent Inc.")
    db_session.add(stock)
    db_session.commit()

    mock_provider = Mock(spec=DataProvider)
    candles = make_daily_candles(50)
    mock_provider.get_daily_candles.return_value = candles

    fetcher = DataFetcher(provider=mock_provider, db=db_session, rate_limit_delay=0)
    fetcher.sync_daily(symbols=["IDEM"])
    fetcher.sync_daily(symbols=["IDEM"])  # second call — same data

    idem = db_session.query(Stock).filter_by(symbol="IDEM").first()
    assert len(idem.daily_candles) == 50  # no duplicates


def test_orm_to_candle_conversion_preserves_precision(db_session: Session):
    """_to_candles() must convert NUMERIC ORM fields to float/int correctly."""
    stock = Stock(symbol="CONV", name="Conversion Co.")
    db_session.add(stock)
    db_session.flush()

    dc = DailyCandle(
        stock_id=stock.id,
        timestamp=datetime(2024, 6, 1),
        open="123.45", high="125.00", low="122.10", close="124.50", volume="987654",
    )
    db_session.add(dc)
    db_session.commit()

    from src.scanner.executor import ScannerExecutor
    from src.output.cli import CLIOutputHandler
    executor = ScannerExecutor(
        registry=ScannerRegistry(),
        indicators_registry={},
        output_handler=CLIOutputHandler(),
        db=db_session,
    )

    from src.scanner.registry import ScannerRegistry as SR
    executor.registry = SR()

    refreshed = db_session.query(Stock).filter_by(symbol="CONV").first()
    candles = executor._to_candles(refreshed.daily_candles)
    assert len(candles) == 1
    assert isinstance(candles[0].close, float)
    assert isinstance(candles[0].volume, int)
    assert abs(candles[0].close - 124.50) < 1e-6
```

- [x] **Step 3: Run end-to-end tests**

```bash
pytest tests/integration/test_end_to_end.py -v
```

Expected output: `3 passed`

- [x] **Step 4: Run complete test suite**

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

Expected output: all tests pass with coverage report.

- [x] **Step 5: Commit**

```bash
git add tests/integration/test_end_to_end.py tests/fixtures/mock_data.py
git commit -m "feat: add E2E integration tests with testcontainers PostgreSQL"
```

---

## Summary

This implementation plan covers the full MVP as 25 concrete TDD-driven tasks:

- Task 1: pyproject.toml + Makefile with all deps (alembic, testcontainers, pytz)
- Task 2: Lazy `get_config()` factory — no module-level DB init at import time
- Task 3: DB connection pooling + testcontainers PostgreSQL `db_session` fixture
- Task 4: All ORM models — `EconomicIndicator`, fixed `JSONB default=dict`, B-tree index replacing BRIN
- Task 5: Alembic migrations wired to `get_config().DATABASE_URL` and `Base.metadata`
- Task 6: `validate_symbol` / `validate_resolution` — called at entry of every provider method
- Task 7: Abstract `DataProvider`, `Candle`, `Quote`, `NewsArticle`, `Earning` dataclasses
- Task 8: `MarketDataAppProvider` — validation calls, `timeout=(5, 30)`, retry with backoff
- Task 9: `Indicator` ABC, `IndicatorCache` (cache-key includes kwargs), `ScanContext`
- Task 10: `SMA`, `EMA` (SMA-seeded warmup, same length as SMA valid), `WMA`
- Task 11: `RSI` (seeded first value from avg gain/loss), `MACD`
- Task 12: `BollingerBands` (returns shape (n,3)), `ATR`
- Task 13: `BreakoutDetector`, `CandlestickPatterns`, `SupportResistance`
- Task 14: Support/resistance (covered in Task 13)
- Task 15: `ScanResult` lives in `scanner/base.py` only; `ScannerRegistry`
- Task 16: `ScannerExecutor` with `_to_candles()` conversion and `_persist_results()` batch commit
- Task 17: `PriceActionScanner` — `logger.exception` replaces `except: pass`
- Task 18: `MomentumScanner` — `logger.exception` replaces `except: pass`
- Task 19: `VolumeScanner` — detects 2× average volume spikes
- Task 20: `OutputHandler`, `Alert`, `CLIOutputHandler`, `LogFileOutputHandler`, `CompositeOutputHandler` (exception logging); `output/base.py` imports `ScanResult` from `scanner/base.py`
- Task 21: `DataFetcher` — `_bulk_upsert_daily_candles`, `sync_intraday`, `sync_news`, `sync_earnings`, `rate_limit_delay`
- Task 22: `create_eod_scheduler` — APScheduler BlockingScheduler, 4:15 PM ET cron
- Task 23: `RealtimeMonitor` — correct `db.query(Stock)`, batch `add_all` per poll cycle; alert rules
- Task 24: `main.py` — fully lazy (no module-level DB init), `eod`, `monitor`, `init-db`, `seed-universe`, `schedule` commands
- Task 25: Integration tests with testcontainers PostgreSQL — E2E pipeline, idempotent upsert, ORM→dataclass conversion
