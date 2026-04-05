"""Scanner executor: runs all registered scanners for stocks with batch commits."""

import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.data_provider.base import Candle
from src.output.base import OutputHandler
from src.scanner.base import ScanResult
from src.scanner.context import ScanContext
from src.scanner.indicators.cache import IndicatorCache
from src.scanner.registry import ScannerRegistry

logger = logging.getLogger(__name__)


class ScannerExecutor:
    """Executes scanners for stocks with batch commits and ORM-to-dataclass conversion."""

    def __init__(
        self,
        registry: ScannerRegistry,
        indicators_registry: Dict,
        output_handler: OutputHandler,
        db: Optional[Session] = None,
    ):
        """Initialize executor with registry, indicators, output handler, and optional DB session."""
        self.registry = registry
        self.indicators_registry = indicators_registry
        self.output_handler = output_handler
        self.db = db

    def _to_candles(self, orm_candles) -> List[Candle]:
        """Convert ORM DailyCandle objects to Candle dataclasses with float/int conversion."""
        return [
            Candle(
                timestamp=c.timestamp,
                open=float(c.open),
                high=float(c.high),
                low=float(c.low),
                close=float(c.close),
                volume=int(c.volume),
            )
            for c in orm_candles
        ]

    def run_eod(
        self,
        stocks_with_candles: Dict[int, tuple],
    ) -> List[ScanResult]:
        """Run all scanners for each stock. Batch-commit all results per stock."""
        all_results: List[ScanResult] = []

        for stock_id, (symbol, daily_candles) in stocks_with_candles.items():
            indicator_cache = IndicatorCache(self.indicators_registry)
            context = ScanContext(
                stock_id=stock_id,
                symbol=symbol,
                daily_candles=daily_candles,
                intraday_candles={},
                indicator_cache=indicator_cache,
            )

            stock_results: List[ScanResult] = []

            for scanner_name, scanner in self.registry.list().items():
                try:
                    results = scanner.scan(context)
                    for result in results:
                        stock_results.append(result)
                        all_results.append(result)
                        self.output_handler.emit_scan_result(result)
                except Exception:
                    logger.exception(f"{scanner_name} failed for {symbol}")

            if stock_results:
                self._persist_results(stock_results)

        return all_results

    def _persist_results(self, results: List[ScanResult]) -> None:
        """Batch insert scanner results into the database."""
        if not results or not self.db:
            return
        from src.db.models import ScannerResult as ScannerResultModel

        self.db.add_all(
            [
                ScannerResultModel(
                    stock_id=r.stock_id,
                    scanner_name=r.scanner_name,
                    result_metadata=r.metadata,
                    matched_at=r.matched_at,
                )
                for r in results
            ]
        )
        self.db.commit()
