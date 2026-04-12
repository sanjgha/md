"""Integration tests for EOD watchlist generation workflow."""

from datetime import date, datetime, timedelta
from typing import cast
from unittest.mock import Mock

from sqlalchemy.orm import Session

from src.api.watchlists.service import WatchlistGenerationService
from src.data_fetcher.fetcher import DataFetcher
from src.data_provider.base import DataProvider
from src.db.models import ScannerResult, Stock, User, Watchlist, WatchlistSymbol
from src.output.cli import CLIOutputHandler
from src.scanner.executor import ScannerExecutor
from src.scanner.indicators.moving_averages import SMA
from src.scanner.registry import ScannerRegistry
from src.scanner.scanners import PriceActionScanner
from tests.fixtures.mock_data import make_daily_candles


def test_eod_watchlist_generation_workflow(db_session: Session):
    """Test complete EOD workflow with watchlist generation.

    1. Seed stock universe with a user
    2. Mock fetch daily candles
    3. Run scanners
    4. Verify watchlists are auto-generated from scanner results
    """
    # 1. Create a user
    user = User(username="test_user", password_hash="test_hash")
    db_session.add(user)
    db_session.commit()

    # 2. Seed stock universe
    stock = Stock(symbol="E2E", name="End-to-End Corp", sector="Test")
    db_session.add(stock)
    db_session.commit()

    # 3. Mock provider returns daily candles
    mock_provider = Mock(spec=DataProvider)
    mock_provider.get_daily_candles.return_value = make_daily_candles(250)
    mock_provider.get_earnings_history.return_value = []

    # 4. Fetch and upsert
    fetcher = DataFetcher(provider=mock_provider, db=db_session, rate_limit_delay=0)
    fetcher.sync_daily(symbols=["E2E"])

    refreshed = db_session.query(Stock).filter_by(symbol="E2E").first()
    assert refreshed is not None, "Stock should exist after sync"
    assert len(refreshed.daily_candles) == 250

    # 5. Build scanner machinery
    scanner_registry = ScannerRegistry()
    scanner_registry.register("price_action", PriceActionScanner())

    indicators = {"sma": SMA()}
    output = CLIOutputHandler()
    executor = ScannerExecutor(
        registry=scanner_registry,
        indicators_registry=indicators,
        output_handler=output,
        db=db_session,
    )

    candles = executor._to_candles(sorted(refreshed.daily_candles, key=lambda c: c.timestamp))
    stocks_with_candles = {cast(int, refreshed.id): ("E2E", candles)}  # type: ignore[union-attr]

    # 6. Run scanners
    results = executor.run_eod(stocks_with_candles)

    # 7. Verify scanner results exist
    assert isinstance(results, list)
    stored = db_session.query(ScannerResult).filter_by(stock_id=refreshed.id).all()  # type: ignore[union-attr]
    assert len(stored) == len(results)

    # 8. Generate watchlists from scanner results
    if results:
        watchlist_service = WatchlistGenerationService(db_session)

        # Group results by scanner
        scanner_names = set(r.scanner_name for r in results)

        for scanner_name in scanner_names:
            watchlist = watchlist_service.generate_from_scanner_results(
                scanner_name=scanner_name,
                scan_date=date.today(),
                user_id=cast(int, user.id),
            )
            if watchlist:
                assert watchlist.name == "Price Action - Today"
                assert watchlist.is_auto_generated is True
                assert watchlist.scanner_name == scanner_name
                assert watchlist.watchlist_mode == "replace"

        # 9. Verify watchlists were created
        watchlists = db_session.query(Watchlist).filter_by(user_id=cast(int, user.id)).all()
        assert len(watchlists) > 0

        # Verify at least one watchlist has symbols
        watchlist_with_symbols = [w for w in watchlists if w.symbols]
        assert len(watchlist_with_symbols) > 0


def test_watchlist_generation_handles_no_results(db_session: Session):
    """Test that watchlist generation handles case with no scanner results gracefully."""
    # Create a user
    user = User(username="test_user", password_hash="test_hash")
    db_session.add(user)
    db_session.commit()

    # Try to generate watchlist with no scanner results
    watchlist_service = WatchlistGenerationService(db_session)

    watchlist = watchlist_service.generate_from_scanner_results(
        scanner_name="price_action",
        scan_date=date.today(),
        user_id=cast(int, user.id),
    )

    # Should return None when no results exist
    assert watchlist is None


def test_watchlist_generation_handles_multiple_scanners(db_session: Session):
    """Test that watchlist generation creates separate watchlists for each scanner."""
    # Create a user
    user = User(username="test_user", password_hash="test_hash")
    db_session.add(user)
    db_session.commit()

    # Create scanner results for multiple scanners
    stock1 = Stock(symbol="AAPL", name="Apple Inc.")
    stock2 = Stock(symbol="MSFT", name="Microsoft Corp.")
    db_session.add_all([stock1, stock2])
    db_session.commit()

    # Create scanner results for price_action scanner
    result1 = ScannerResult(
        stock_id=stock1.id,
        scanner_name="price_action",
        result_metadata={"reason": "SMA crossover"},
        matched_at=datetime.now(),
    )
    db_session.add(result1)

    # Create scanner results for momentum scanner
    result2 = ScannerResult(
        stock_id=stock2.id,
        scanner_name="momentum",
        result_metadata={"reason": "RSI oversold"},
        matched_at=datetime.now(),
    )
    db_session.add(result2)
    db_session.commit()

    # Generate watchlists
    watchlist_service = WatchlistGenerationService(db_session)

    watchlist1 = watchlist_service.generate_from_scanner_results(
        scanner_name="price_action",
        scan_date=date.today(),
        user_id=cast(int, user.id),
    )

    watchlist2 = watchlist_service.generate_from_scanner_results(
        scanner_name="momentum",
        scan_date=date.today(),
        user_id=cast(int, user.id),
    )

    # Verify both watchlists were created
    assert watchlist1 is not None
    assert watchlist2 is not None
    assert watchlist1.name == "Price Action - Today"
    assert watchlist2.name == "Momentum - Today"

    # Verify they have different scanner names
    assert watchlist1.scanner_name == "price_action"
    assert watchlist2.scanner_name == "momentum"


def test_generate_twice_replaces_today_and_appends_history(db_session: Session):
    """Second EOD run replaces Today symbols and accumulates History symbols (no duplicates)."""
    user = User(username="eod_user2", password_hash="hash")
    db_session.add(user)
    stock_a = Stock(symbol="RUN1", name="Run One")
    stock_b = Stock(symbol="RUN2", name="Run Two")
    db_session.add_all([stock_a, stock_b])
    db_session.commit()

    # First run: only stock_a matches (yesterday's scan)
    yesterday = date.today() - timedelta(days=1)
    result1 = ScannerResult(
        stock_id=stock_a.id,
        scanner_name="momentum",
        result_metadata={"reason": "day1"},
        matched_at=datetime.combine(yesterday, datetime.min.time()),
    )
    db_session.add(result1)
    db_session.commit()

    svc = WatchlistGenerationService(db_session)
    svc.generate_from_scanner_results("momentum", yesterday, cast(int, user.id))

    # Verify Today has 1 symbol, History has 1 symbol
    today_wl = db_session.query(Watchlist).filter_by(
        user_id=user.id, scanner_name="momentum", watchlist_mode="replace"
    ).first()
    history_wl = db_session.query(Watchlist).filter_by(
        user_id=user.id, scanner_name="momentum", watchlist_mode="append"
    ).first()
    assert today_wl is not None
    assert history_wl is not None
    assert db_session.query(WatchlistSymbol).filter_by(watchlist_id=today_wl.id).count() == 1
    assert db_session.query(WatchlistSymbol).filter_by(watchlist_id=history_wl.id).count() == 1

    # Second run: only stock_b matches (different stock)
    result2 = ScannerResult(
        stock_id=stock_b.id,
        scanner_name="momentum",
        result_metadata={"reason": "day2"},
        matched_at=datetime.now(),
    )
    db_session.add(result2)
    db_session.commit()

    svc.generate_from_scanner_results("momentum", date.today(), cast(int, user.id))

    db_session.expire_all()
    # Today must have exactly 1 symbol (stock_b only — replaced, not accumulated)
    assert db_session.query(WatchlistSymbol).filter_by(watchlist_id=today_wl.id).count() == 1
    today_sym = db_session.query(WatchlistSymbol).filter_by(watchlist_id=today_wl.id).first()
    assert today_sym.stock_id == stock_b.id

    # History must have 2 symbols (stock_a from run1, stock_b from run2)
    assert db_session.query(WatchlistSymbol).filter_by(watchlist_id=history_wl.id).count() == 2

    # No duplicate watchlists created
    assert db_session.query(Watchlist).filter_by(
        user_id=user.id, scanner_name="momentum", watchlist_mode="replace"
    ).count() == 1
    assert db_session.query(Watchlist).filter_by(
        user_id=user.id, scanner_name="momentum", watchlist_mode="append"
    ).count() == 1
