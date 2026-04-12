"""Integration tests for EOD watchlist generation workflow."""

from datetime import date, datetime
from typing import cast
from unittest.mock import Mock

from sqlalchemy.orm import Session

from src.api.watchlists.service import WatchlistGenerationService
from src.data_fetcher.fetcher import DataFetcher
from src.data_provider.base import DataProvider
from src.db.models import ScannerResult, Stock, User, Watchlist
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

    refreshed = db_session.query(Stock).filter_by(symbol="E2E").first()  # type: ignore[union-attr]
    assert len(refreshed.daily_candles) == 250  # type: ignore[union-attr]

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
