"""Integration tests: ema_pullback_rs through ScannerExecutor with real Postgres."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

import numpy as np
from sqlalchemy import select

from src.db.models import DailyCandle, ScannerResult, Stock
from src.output.base import OutputHandler
from src.scanner.executor import ScannerExecutor
from src.scanner.indicators.moving_averages import EMA
from src.scanner.indicators.momentum import RSI
from src.scanner.indicators.volatility import ATR
from src.scanner.registry import ScannerRegistry
from src.scanner.scanners.ema_pullback_rs import EmaPullbackRsScanner


class NullOutput(OutputHandler):
    """No-op output handler — integration tests inspect DB directly."""

    def emit_scan_result(self, result):
        pass

    def emit_alert(self, alert):
        pass


def _seed_stock_with_candles(db, ticker: str, closes: List[float], start: datetime) -> int:
    """Insert a Stock + matching DailyCandle rows. Returns stock_id.

    Note: Stock column is `symbol`, but we keep the param name `ticker` for clarity at call sites.
    """
    stock = Stock(symbol=ticker)
    db.add(stock)
    db.flush()
    for i, close in enumerate(closes):
        db.add(
            DailyCandle(
                stock_id=stock.id,
                timestamp=start + timedelta(days=i),
                open=Decimal(f"{close * 0.999:.2f}"),
                high=Decimal(f"{close * 1.005:.2f}"),
                low=Decimal(f"{close * 0.995:.2f}"),
                close=Decimal(f"{close:.2f}"),
                volume=5_000_000,
            )
        )
    db.commit()
    return stock.id


def _happy_path_closes(n: int = 280) -> List[float]:
    """Build closes that drive the scanner through all 5 gates and emit a result.

    Mirrors the unit-test fixture _uptrend_with_pullback() but exposed as a flat closes list.
    """
    rng = np.random.default_rng(seed=42)
    closes = list(np.linspace(50, 150, n - 5) + rng.normal(0, 0.5, n - 5))
    # Manually craft the last 5 bars to engineer a touch + reclaim.
    closes += [
        closes[-1] * 0.99,
        closes[-1] * 0.96,
        closes[-1] * 0.96,
        closes[-1] * 0.98,
        closes[-1] * 1.012,
    ]
    return closes


def test_eod_run_persists_ema_pullback_rs_result(db_session):
    """Full path: stock + SPY in DB → ScannerExecutor.run_eod → scanner_results row written."""
    start = datetime(2024, 1, 1)
    stock_closes = _happy_path_closes()
    spy_closes = list(np.linspace(100, 110, len(stock_closes)))
    stock_id = _seed_stock_with_candles(db_session, "AAA", stock_closes, start)
    _seed_stock_with_candles(db_session, "SPY", spy_closes, start)

    registry = ScannerRegistry()
    registry.register("ema_pullback_rs", EmaPullbackRsScanner())
    executor = ScannerExecutor(
        registry=registry,
        indicators_registry={"ema": EMA(), "rsi": RSI(), "atr": ATR()},
        output_handler=NullOutput(),
        db=db_session,
    )

    aaa_orm = (
        db_session.execute(
            select(DailyCandle)
            .where(DailyCandle.stock_id == stock_id)
            .order_by(DailyCandle.timestamp)
        )
        .scalars()
        .all()
    )
    daily = executor._to_candles(aaa_orm)
    executor.run_eod({stock_id: ("AAA", daily)})

    rows = (
        db_session.execute(
            select(ScannerResult).where(ScannerResult.scanner_name == "ema_pullback_rs")
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    md = rows[0].result_metadata
    assert md["benchmark_symbol"] == "SPY"
    assert 40 <= md["rsi_14"] <= 70
    assert md["mansfield_rs"] > 0
    assert md["pullback_touch_idx_offset"] < 0
    assert "signal_date" in md


def test_eod_run_emits_nothing_when_benchmark_missing(db_session):
    """No SPY in stocks table → scanner returns [] for every stock, no error."""
    start = datetime(2024, 1, 1)
    stock_id = _seed_stock_with_candles(db_session, "AAA", _happy_path_closes(), start)

    registry = ScannerRegistry()
    registry.register("ema_pullback_rs", EmaPullbackRsScanner())
    executor = ScannerExecutor(
        registry=registry,
        indicators_registry={"ema": EMA(), "rsi": RSI(), "atr": ATR()},
        output_handler=NullOutput(),
        db=db_session,
    )

    aaa_orm = (
        db_session.execute(
            select(DailyCandle)
            .where(DailyCandle.stock_id == stock_id)
            .order_by(DailyCandle.timestamp)
        )
        .scalars()
        .all()
    )
    daily = executor._to_candles(aaa_orm)
    executor.run_eod({stock_id: ("AAA", daily)})

    rows = (
        db_session.execute(
            select(ScannerResult).where(ScannerResult.scanner_name == "ema_pullback_rs")
        )
        .scalars()
        .all()
    )
    assert rows == []
