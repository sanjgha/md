"""End-to-end integration tests: fetch → upsert → scan → verify DB results."""

from datetime import datetime
from typing import cast
from unittest.mock import Mock

from sqlalchemy.orm import Session

from src.data_fetcher.fetcher import DataFetcher
from src.data_provider.base import DataProvider
from src.db.models import DailyCandle, ScannerResult, Stock
from src.output.cli import CLIOutputHandler
from src.scanner.executor import ScannerExecutor
from src.scanner.indicators.momentum import RSI
from src.scanner.indicators.moving_averages import EMA, SMA
from src.scanner.indicators.support_resistance import SupportResistance
from src.scanner.indicators.volatility import ATR, BollingerBands
from src.scanner.registry import ScannerRegistry
from src.scanner.scanners import MomentumScanner, PriceActionScanner, VolumeScanner
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

    refreshed = db_session.query(Stock).filter_by(symbol="E2E").first()  # type: ignore[union-attr]
    assert len(refreshed.daily_candles) == 250  # type: ignore[union-attr]

    # 4. Build scanner machinery
    scanner_registry = ScannerRegistry()
    scanner_registry.register("price_action", PriceActionScanner())
    scanner_registry.register("momentum", MomentumScanner())
    scanner_registry.register("volume", VolumeScanner())

    indicators = {
        "sma": SMA(),
        "ema": EMA(),
        "rsi": RSI(),
        "bollinger": BollingerBands(),
        "atr": ATR(),
        "support_resistance": SupportResistance(),
    }
    output = CLIOutputHandler()
    executor = ScannerExecutor(
        registry=scanner_registry,
        indicators_registry=indicators,
        output_handler=output,
        db=db_session,
    )

    candles = executor._to_candles(sorted(refreshed.daily_candles, key=lambda c: c.timestamp))  # type: ignore[union-attr]
    stocks_with_candles = {cast(int, refreshed.id): ("E2E", candles)}  # type: ignore[union-attr]

    # 5. Run scanners
    results = executor.run_eod(stocks_with_candles)  # type: ignore[union-attr]

    # 6. Verify pipeline ran to completion
    assert isinstance(results, list)
    stored = db_session.query(ScannerResult).filter_by(stock_id=refreshed.id).all()  # type: ignore[union-attr]
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
    assert idem is not None, "Stock should exist after sync"
    assert len(idem.daily_candles) == 50  # no duplicates


def test_orm_to_candle_conversion_preserves_precision(db_session: Session):
    """_to_candles() must convert NUMERIC ORM fields to float/int correctly."""
    stock = Stock(symbol="CONV", name="Conversion Co.")
    db_session.add(stock)
    db_session.flush()

    dc = DailyCandle(
        stock_id=cast(int, stock.id),
        timestamp=datetime(2024, 6, 1),
        open="123.45",
        high="125.00",
        low="122.10",
        close="124.50",
        volume="987654",
    )
    db_session.add(dc)
    db_session.commit()

    executor = ScannerExecutor(
        registry=ScannerRegistry(),
        indicators_registry={},
        output_handler=CLIOutputHandler(),
        db=db_session,
    )

    refreshed = db_session.query(Stock).filter_by(symbol="CONV").first()  # type: ignore[union-attr]
    assert refreshed is not None  # type: ignore[union-attr]
    candles = executor._to_candles(refreshed.daily_candles)  # type: ignore[union-attr]
    assert len(candles) == 1
    assert isinstance(candles[0].close, float)
    assert isinstance(candles[0].volume, int)
    assert abs(candles[0].close - 124.50) < 1e-6
