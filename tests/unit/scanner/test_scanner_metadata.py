"""Tests for scanner ABC metadata attributes."""

from src.scanner.scanners.momentum_scan import MomentumScanner
from src.scanner.scanners.price_action import PriceActionScanner
from src.scanner.scanners.volume_scan import VolumeScanner


def test_momentum_scanner_metadata():
    s = MomentumScanner()
    assert s.timeframe == "daily"
    assert isinstance(s.description, str)
    assert len(s.description) > 0


def test_price_action_scanner_metadata():
    s = PriceActionScanner()
    assert s.timeframe == "daily"
    assert isinstance(s.description, str)
    assert len(s.description) > 0


def test_volume_scanner_metadata():
    s = VolumeScanner()
    assert s.timeframe == "daily"
    assert isinstance(s.description, str)
    assert len(s.description) > 0
