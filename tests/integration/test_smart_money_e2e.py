"""Integration tests for SmartMoneyScanner — full scanner pipeline."""

from src.scanner.scanners.smart_money import SmartMoneyScanner
from src.scanner.registry import ScannerRegistry
from src.scanner.context import ScanContext
from src.data_provider.base import Candle
from datetime import datetime, timedelta
from unittest.mock import Mock
from src.scanner.indicators.cache import IndicatorCache


def create_candle(open_price, high, low, close, volume, days_ago):
    """Helper to create a candle with timestamp days_ago from now."""
    ts = datetime.utcnow() - timedelta(days=days_ago)
    return Candle(timestamp=ts, open=open_price, high=high, low=low, close=close, volume=volume)


def create_mock_context(candles):
    """Create a ScanContext with mock candles."""
    cache = IndicatorCache(indicators_registry={})
    context = Mock(spec=ScanContext)
    context.stock_id = 1
    context.symbol = "TEST"
    context.daily_candles = candles
    context.intraday_candles = {}
    context.indicator_cache = cache

    def get_indicator_side_effect(name, **kwargs):
        return cache.get_or_compute(name, candles, **kwargs)

    context.get_indicator = get_indicator_side_effect

    return context


def test_full_scanner_pipeline_with_mock_data():
    """Test full scanner pipeline: registration, retrieval, and basic properties.

    This integration test verifies:
    - ScannerRegistry can register SmartMoneyScanner
    - Scanner is retrievable by name
    - Scanner has correct timeframe and description
    - Scanner can be instantiated and scanned (even if no matches)

    TODO: Add full e2e test with complete FVG+MSS pattern that generates matches.
    """
    # Step 1: Create ScannerRegistry
    registry = ScannerRegistry()

    # Step 2: Register SmartMoneyScanner
    scanner = SmartMoneyScanner()
    scanner_name = "smart_money"
    registry.register(scanner_name, scanner)

    # Step 3: Verify scanner is retrieved successfully
    retrieved_scanner = registry.get(scanner_name)
    assert retrieved_scanner is not None, "Scanner should be retrievable from registry"
    assert retrieved_scanner is scanner, "Retrieved scanner should be same instance"

    # Step 4: Verify scanner properties
    assert retrieved_scanner.timeframe == "daily", (
        f"Expected timeframe 'daily', got '{retrieved_scanner.timeframe}'"
    )
    assert retrieved_scanner.description == "ICT-style FVG + MSS entry detection (50-79% zone)", (
        f"Unexpected description: '{retrieved_scanner.description}'"
    )

    # Step 5: Verify scanner can be scanned (even with insufficient data)
    # Create minimal context (insufficient candles for actual detection)
    candles = [
        create_candle(100, 105, 95, 100, 1000, 5),
        create_candle(100, 105, 95, 100, 1100, 4),
        create_candle(100, 105, 95, 100, 1200, 3),
    ]
    context = create_mock_context(candles)

    # Scanner should run without errors (return empty list due to insufficient candles)
    results = retrieved_scanner.scan(context)
    assert isinstance(results, list), "Scan should return a list"
    assert len(results) == 0, "Insufficient candles should yield no matches"

    # Step 6: Verify scanner appears in registry listing
    all_scanners = registry.list()
    assert scanner_name in all_scanners, "Scanner should appear in registry listing"
    assert all_scanners[scanner_name] is scanner, "Listed scanner should be same instance"


def test_scanner_registry_multiple_scanners():
    """Test that SmartMoneyScanner coexists with other scanners in registry."""
    registry = ScannerRegistry()

    # Register multiple scanners
    smart_money_scanner = SmartMoneyScanner()
    registry.register("smart_money", smart_money_scanner)

    # Mock another scanner
    from src.scanner.base import Scanner

    class MockScanner(Scanner):
        timeframe = "4h"
        description = "Mock scanner for testing"

        def scan(self, context):
            return []

    mock_scanner = MockScanner()
    registry.register("mock_scanner", mock_scanner)

    # Verify both are registered
    assert registry.get("smart_money") is smart_money_scanner
    assert registry.get("mock_scanner") is mock_scanner

    # Verify listing includes both
    all_scanners = registry.list()
    assert len(all_scanners) == 2
    assert "smart_money" in all_scanners
    assert "mock_scanner" in all_scanners


def test_scanner_properties_match_requirements():
    """Verify SmartMoneyScanner has all required properties and attributes."""
    scanner = SmartMoneyScanner()

    # Check class attributes
    assert hasattr(scanner, "timeframe"), "Scanner should have timeframe attribute"
    assert hasattr(scanner, "description"), "Scanner should have description attribute"
    assert hasattr(scanner, "scan"), "Scanner should have scan method"
    assert hasattr(scanner, "detect_bos"), "Scanner should have detect_bos method"
    assert hasattr(scanner, "detect_mss"), "Scanner should have detect_mss method"
    assert hasattr(scanner, "calculate_fib_levels"), (
        "Scanner should have calculate_fib_levels method"
    )

    # Check constants
    assert hasattr(scanner, "MIN_CANDLES"), "Scanner should have MIN_CANDLES constant"
    assert hasattr(scanner, "MSS_LOOKBACK"), "Scanner should have MSS_LOOKBACK constant"
    assert hasattr(scanner, "MIN_FVG_GAP_PCT"), "Scanner should have MIN_FVG_GAP_PCT constant"
    assert hasattr(scanner, "MAX_MERGED_ZONE_PCT"), (
        "Scanner should have MAX_MERGED_ZONE_PCT constant"
    )

    # Verify values
    assert scanner.MIN_CANDLES == 100, "MIN_CANDLES should be 100"
    assert scanner.MSS_LOOKBACK == 20, "MSS_LOOKBACK should be 20"
    assert scanner.MIN_FVG_GAP_PCT == 0.75, "MIN_FVG_GAP_PCT should be 0.75"
    assert scanner.MAX_MERGED_ZONE_PCT == 5.0, "MAX_MERGED_ZONE_PCT should be 5.0"
