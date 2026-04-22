"""Job callbacks for scheduled scanner runs.

Each function accepts a SQLAlchemy Session and returns the number of matched results.
These are called both by the BackgroundScheduler and by POST /run (synchronously).
"""

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _build_indicator_registry() -> dict:
    from src.scanner.indicators.moving_averages import SMA, EMA, WMA
    from src.scanner.indicators.momentum import RSI, MACD
    from src.scanner.indicators.volatility import BollingerBands, ATR
    from src.scanner.indicators.support_resistance import SupportResistance
    from src.scanner.indicators.patterns.breakouts import BreakoutDetector

    return {
        "sma": SMA(),
        "ema": EMA(),
        "wma": WMA(),
        "rsi": RSI(),
        "macd": MACD(),
        "bollinger": BollingerBands(),
        "atr": ATR(),
        "support_resistance": SupportResistance(),
        "breakout": BreakoutDetector(),
    }


def _build_scanner_registry():
    from src.scanner.registry import ScannerRegistry
    from src.scanner.scanners import PriceActionScanner, MomentumScanner, VolumeScanner

    registry = ScannerRegistry()
    registry.register("price_action", PriceActionScanner())
    registry.register("momentum", MomentumScanner())
    registry.register("volume", VolumeScanner())
    return registry


def _build_output_handler():
    from src.output.logger import LogFileOutputHandler
    from src.output.composite import CompositeOutputHandler
    from src.config import get_config

    cfg = get_config()
    return CompositeOutputHandler(
        [LogFileOutputHandler(log_file=cfg.LOG_FILE, log_level=cfg.LOG_LEVEL)]
    )


def run_eod_job(db: Session) -> int:
    """Run EOD scan against daily candles. Returns count of matched results."""
    from src.scanner.executor import ScannerExecutor
    from src.db.models import Stock
    from sqlalchemy.orm import joinedload

    indicators = _build_indicator_registry()
    registry = _build_scanner_registry()
    output = _build_output_handler()

    stocks = db.query(Stock).options(joinedload(Stock.daily_candles)).all()
    executor = ScannerExecutor(
        registry=registry,
        indicators_registry=indicators,
        output_handler=output,
        db=db,
    )
    stocks_with_candles = {
        int(s.id): (
            str(s.symbol),
            executor._to_candles(sorted(s.daily_candles, key=lambda c: c.timestamp)),
        )
        for s in stocks
        if s.daily_candles
    }
    results = executor.run_eod(stocks_with_candles)
    logger.info("EOD job complete: %d results", len(results))
    return len(results)


def run_pre_close_job(db: Session) -> int:
    """Run pre-close scan using realtime quotes. Returns count of matched results."""
    from src.scanner.pre_close_executor import PreCloseExecutor

    indicators = _build_indicator_registry()
    registry = _build_scanner_registry()
    output = _build_output_handler()

    executor = PreCloseExecutor(
        registry=registry,
        indicators_registry=indicators,
        output_handler=output,
        db=db,
    )
    results = executor.run()
    logger.info("Pre-close job complete: %d results", len(results))
    return len(results)


def run_quote_polling_job(db: Session) -> int:
    """Run quote polling job. Returns count of quotes fetched."""
    from src.workers.quote_worker import QuoteWorker
    from src.data_provider.marketdata_app import MarketDataAppProvider
    from src.config import get_config

    cfg = get_config()
    provider = MarketDataAppProvider(api_token=cfg.MARKETDATA_API_TOKEN)

    # Use global cache service instance (will be created in manager)
    from src.api.schedule.manager import get_quote_cache_service

    cache_service = get_quote_cache_service()

    worker = QuoteWorker(db, cache_service, provider)
    return worker.poll()
