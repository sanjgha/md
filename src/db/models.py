"""SQLAlchemy ORM models for market data infrastructure."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    NUMERIC,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


class Stock(Base):
    """Stock universe reference table."""

    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255))
    sector = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    daily_candles = relationship(
        "DailyCandle", back_populates="stock", cascade="all, delete-orphan"
    )
    intraday_candles = relationship(
        "IntradayCandle", back_populates="stock", cascade="all, delete-orphan"
    )
    realtime_quotes = relationship(
        "RealtimeQuote", back_populates="stock", cascade="all, delete-orphan"
    )
    earnings = relationship(
        "EarningsCalendar", back_populates="stock", cascade="all, delete-orphan"
    )
    news = relationship("StockNews", back_populates="stock", cascade="all, delete-orphan")
    options = relationship("OptionsQuote", back_populates="stock", cascade="all, delete-orphan")
    scanner_results = relationship(
        "ScannerResult", back_populates="stock", cascade="all, delete-orphan"
    )


class DailyCandle(Base):
    """Daily OHLCV data (1-year retention)."""

    __tablename__ = "daily_candles"

    id = Column(BigInteger, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open: Column[Decimal] = Column(NUMERIC(10, 2), nullable=False)
    high: Column[Decimal] = Column(NUMERIC(10, 2), nullable=False)
    low: Column[Decimal] = Column(NUMERIC(10, 2), nullable=False)
    close: Column[Decimal] = Column(NUMERIC(10, 2), nullable=False)
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
    open: Column[Decimal] = Column(NUMERIC(10, 2), nullable=False)
    high: Column[Decimal] = Column(NUMERIC(10, 2), nullable=False)
    low: Column[Decimal] = Column(NUMERIC(10, 2), nullable=False)
    close: Column[Decimal] = Column(NUMERIC(10, 2), nullable=False)
    volume = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "resolution",
            "timestamp",
            name="uq_intraday_candles_stock_res_ts",
        ),
        Index("ix_intraday_candles_stock_ts", "stock_id", "timestamp"),
        Index("ix_intraday_candles_stock_res_ts", "stock_id", "resolution", "timestamp"),
    )

    stock = relationship("Stock", back_populates="intraday_candles")


class RealtimeQuote(Base):
    """Realtime quotes with intraday summary (7-day retention)."""

    __tablename__ = "realtime_quotes"

    id = Column(BigInteger, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    bid: Column[Decimal | None] = Column(NUMERIC(10, 2))
    ask: Column[Decimal | None] = Column(NUMERIC(10, 2))
    bid_size = Column(BigInteger)
    ask_size = Column(BigInteger)
    last: Column[Decimal | None] = Column(NUMERIC(10, 2))
    open: Column[Decimal | None] = Column(NUMERIC(10, 2))
    high: Column[Decimal | None] = Column(NUMERIC(10, 2))
    low: Column[Decimal | None] = Column(NUMERIC(10, 2))
    close: Column[Decimal | None] = Column(NUMERIC(10, 2))
    volume = Column(BigInteger)
    change: Column[Decimal | None] = Column(NUMERIC(10, 4))
    change_pct: Column[Decimal | None] = Column(NUMERIC(10, 4))
    week_52_high: Column[Decimal | None] = Column(NUMERIC(10, 2))
    week_52_low: Column[Decimal | None] = Column(NUMERIC(10, 2))
    status = Column(String(50))
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_realtime_quotes_stock_ts", "stock_id", "timestamp"),)

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
    reported_eps: Column[Decimal | None] = Column(NUMERIC(10, 4))
    estimated_eps: Column[Decimal | None] = Column(NUMERIC(10, 4))
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
        UniqueConstraint(
            "stock_id",
            "source",
            "publication_date",
            name="uq_stock_news_stock_src_date",
        ),
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
    bid: Column[Decimal | None] = Column(NUMERIC(10, 2))
    ask: Column[Decimal | None] = Column(NUMERIC(10, 2))
    bid_size = Column(BigInteger)
    ask_size = Column(BigInteger)
    last: Column[Decimal | None] = Column(NUMERIC(10, 2))
    volume = Column(BigInteger)
    open_interest = Column(BigInteger)
    delta: Column[Decimal | None] = Column(NUMERIC(10, 4))
    gamma: Column[Decimal | None] = Column(NUMERIC(10, 4))
    theta: Column[Decimal | None] = Column(NUMERIC(10, 4))
    vega: Column[Decimal | None] = Column(NUMERIC(10, 4))
    iv: Column[Decimal | None] = Column(NUMERIC(10, 4))
    underlying_price: Column[Decimal | None] = Column(NUMERIC(10, 2))
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
    result_metadata: Column[dict] = Column(
        JSONB, default=dict
    )  # callable — not a shared mutable default
    matched_at = Column(DateTime, nullable=False)
    run_type = Column(String(20), nullable=False, default="eod")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_scanner_results_name_ts", "scanner_name", "matched_at"),
        Index("ix_scanner_results_stock_ts", "stock_id", "matched_at"),
    )

    stock = relationship("Stock", back_populates="scanner_results")


class ScheduleConfig(Base):
    """Persists scheduler job configuration across restarts."""

    __tablename__ = "schedule_config"

    job_id: Mapped[str] = mapped_column(Text, primary_key=True)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)
    minute: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_save: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class EconomicIndicator(Base):
    """Macro economic indicator releases."""

    __tablename__ = "economic_indicators"

    id = Column(Integer, primary_key=True)
    indicator_name = Column(String(255), nullable=False)
    release_date = Column(DateTime, nullable=False)
    value: Column[Decimal | None] = Column(NUMERIC(15, 4))
    unit = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "indicator_name",
            "release_date",
            name="uq_economic_indicator_name_date",
        ),
    )


class User(Base):
    """Application user (single-user now; forward-compatible with multi-user)."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    ui_settings = relationship("UiSetting", back_populates="user", cascade="all, delete-orphan")
    watchlists = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")
    watchlist_categories = relationship(
        "WatchlistCategory", back_populates="user", cascade="all, delete-orphan"
    )


class UiSetting(Base):
    """Per-user UI preferences stored as key/JSONB-value pairs."""

    __tablename__ = "ui_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        server_default="1",
    )
    key = Column(String(64), nullable=False)
    value: Column[dict] = Column(JSONB, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_ui_settings_user_key"),)

    user = relationship("User", back_populates="ui_settings")


class WatchlistCategory(Base):
    """User-defined categories for organizing watchlists."""

    __tablename__ = "watchlist_categories"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        server_default="1",
    )
    name = Column(String(100), nullable=False)
    description = Column(Text)
    color = Column(String(7))  # Hex color code
    icon = Column(String(50))
    is_system = Column(
        Boolean, default=False, nullable=False
    )  # System categories cannot be deleted
    sort_order = Column(Integer, default=0, nullable=False)  # For ordering categories
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_watchlist_categories_user_name"),
    )

    user = relationship("User", back_populates="watchlist_categories")
    watchlists = relationship("Watchlist", back_populates="category")


class Watchlist(Base):
    """User-defined watchlists for tracking stock symbols."""

    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        server_default="1",
    )
    name = Column(String(100), nullable=False)
    category_id = Column(Integer, ForeignKey("watchlist_categories.id", ondelete="SET NULL"))
    description = Column(Text)
    is_auto_generated = Column(Boolean, default=False, nullable=False)
    scanner_name = Column(String(255))  # If auto-generated, which scanner created it
    watchlist_mode = Column(String(50), default="static")  # static, dynamic, scanner_output
    source_scan_date = Column(DateTime)  # When auto-generated watchlist was created
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_watchlists_user_name"),)

    user = relationship("User", back_populates="watchlists")
    category = relationship("WatchlistCategory", back_populates="watchlists")
    symbols = relationship(
        "WatchlistSymbol", back_populates="watchlist", cascade="all, delete-orphan"
    )


class WatchlistSymbol(Base):
    """Individual stock symbols within a watchlist."""

    __tablename__ = "watchlist_symbols"

    id = Column(Integer, primary_key=True)
    watchlist_id = Column(
        Integer,
        ForeignKey("watchlists.id", ondelete="CASCADE"),
        nullable=False,
    )
    stock_id = Column(
        Integer,
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    notes = Column(Text)
    added_at = Column(DateTime, default=datetime.utcnow)
    priority = Column(Integer, default=0)  # For ordering/sorting

    __table_args__ = (
        UniqueConstraint("watchlist_id", "stock_id", name="uq_watchlist_symbols_watchlist_stock"),
        Index("ix_watchlist_symbols_watchlist_priority", "watchlist_id", "priority"),
    )

    watchlist = relationship("Watchlist", back_populates="symbols")
    stock = relationship("Stock")


class IVRSnapshot(Base):
    """IV Rank snapshots — one row per symbol per date per calculation basis."""

    __tablename__ = "ivr_snapshots"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), nullable=False)
    as_of_date = Column(DateTime, nullable=False)
    ivr: Column[Decimal] = Column(NUMERIC(5, 2), nullable=False)
    current_hv: Column[Decimal] = Column(NUMERIC(8, 4), nullable=False)
    calculation_basis = Column(String(16), nullable=False)  # "hv_proxy" | "implied"
    computed_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "symbol", "as_of_date", "calculation_basis", name="uq_ivr_symbol_date_basis"
        ),
        Index("ix_ivr_symbol", "symbol"),
        Index("ix_ivr_as_of", "as_of_date"),
    )
