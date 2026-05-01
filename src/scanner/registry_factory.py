"""Single source of truth for building the active scanner registry."""

from src.scanner.registry import ScannerRegistry

REGISTERED_SCANNER_NAMES: frozenset[str] = frozenset(
    {"volume", "smart_money", "six_month_high", "weekly_options", "pullback_continuation"}
)


def build_scanner_registry() -> ScannerRegistry:
    """Instantiate and register all active scanners, returning a populated registry."""
    from src.scanner.scanners.volume_scan import VolumeScanner
    from src.scanner.scanners.smart_money import SmartMoneyScanner
    from src.scanner.scanners.six_month_high import SixMonthHighScanner
    from src.scanner.scanners.weekly_options import WeeklyOptionsScanner
    from src.scanner.scanners.pullback_continuation import PullbackContinuationScanner

    registry = ScannerRegistry()
    registry.register("volume", VolumeScanner())
    registry.register("smart_money", SmartMoneyScanner())
    registry.register("six_month_high", SixMonthHighScanner())
    registry.register("weekly_options", WeeklyOptionsScanner())
    registry.register("pullback_continuation", PullbackContinuationScanner())
    return registry
