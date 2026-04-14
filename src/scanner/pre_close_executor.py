"""Pre-close scanner executor: runs scanners using realtime quote data as today's partial candle."""

import logging
from datetime import datetime
from typing import List

from src.data_provider.base import Candle
from src.db.models import RealtimeQuote, Stock
from src.scanner.base import ScanResult
from src.scanner.context import ScanContext
from src.scanner.executor import ScannerExecutor
from src.scanner.indicators.cache import IndicatorCache

logger = logging.getLogger(__name__)


class PreCloseExecutor(ScannerExecutor):
    """Executes scanners using historical candles + today's realtime quote as a partial candle.

    Intended to be run at 3:45 PM ET Mon-Fri to surface pre-close signals before market close.
    Results are persisted with run_type='pre_close' to distinguish from EOD runs.
    """

    def build_contexts(self) -> List[ScanContext]:
        """Build ScanContext list for all stocks that have a current realtime quote.

        Stocks with no realtime quote are silently skipped.
        """
        if not self.db:
            return []

        stocks = self.db.query(Stock).all()
        contexts: List[ScanContext] = []

        for stock in stocks:
            quote: RealtimeQuote | None = (
                self.db.query(RealtimeQuote)
                .filter(RealtimeQuote.stock_id == stock.id)
                .order_by(RealtimeQuote.timestamp.desc())
                .first()
            )

            if quote is None:
                logger.debug(f"No realtime quote for {stock.symbol}, skipping pre-close scan")
                continue

            # Convert historical ORM candles to Candle dataclasses
            historical_candles = self._to_candles(
                sorted(stock.daily_candles, key=lambda c: c.timestamp)
            )

            # Build a partial "today" candle from the realtime quote.
            # Use quote.last as the current close proxy; fall back to 0.0 for missing fields.
            today_candle = Candle(
                timestamp=(
                    quote.timestamp if isinstance(quote.timestamp, datetime) else datetime.utcnow()
                ),
                open=float(quote.open) if quote.open is not None else 0.0,
                high=float(quote.high) if quote.high is not None else 0.0,
                low=float(quote.low) if quote.low is not None else 0.0,
                close=float(quote.last) if quote.last is not None else 0.0,
                volume=int(quote.volume) if quote.volume is not None else 0,
            )

            all_candles = historical_candles + [today_candle]

            indicator_cache = IndicatorCache(self.indicators_registry)
            context = ScanContext(
                stock_id=int(stock.id),
                symbol=str(stock.symbol),
                daily_candles=all_candles,
                intraday_candles={},
                indicator_cache=indicator_cache,
            )
            contexts.append(context)

        return contexts

    def run(self) -> List[ScanResult]:
        """Run all registered scanners using pre-close contexts.

        Persists results with run_type='pre_close'. Returns all matched results.
        """
        contexts = self.build_contexts()
        all_results: List[ScanResult] = []

        for context in contexts:
            stock_results: List[ScanResult] = []

            for scanner_name, scanner in self.registry.list().items():
                try:
                    results = scanner.scan(context)
                    for result in results:
                        stock_results.append(result)
                        all_results.append(result)
                        self.output_handler.emit_scan_result(result)
                except Exception:
                    logger.exception(
                        f"{scanner_name} failed for {context.symbol} during pre-close scan"
                    )

            if stock_results:
                self._persist_results(stock_results, run_type="pre_close")

        return all_results
