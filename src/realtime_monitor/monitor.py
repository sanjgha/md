"""Realtime monitor: polls quotes and fires alerts with batch commits."""

import logging
import time
from datetime import datetime
from typing import Optional, Set

from sqlalchemy.orm import Session, joinedload

from src.data_provider.base import DataProvider
from src.db.models import RealtimeQuote as RealtimeQuoteModel
from src.db.models import ScannerResult, Stock
from src.output.base import Alert, OutputHandler
from src.realtime_monitor.alert_engine import AlertEngine

logger = logging.getLogger(__name__)


class RealtimeMonitor:
    """Monitors matched tickers from EOD scanner, stores quotes, fires alerts."""

    def __init__(
        self,
        provider: DataProvider,
        db: Session,
        output_handler: OutputHandler,
        alert_engine: AlertEngine,
    ):
        """Initialize monitor with provider, DB session, output handler, and alert engine."""
        self.provider = provider
        self.db = db
        self.output_handler = output_handler
        self.alert_engine = alert_engine
        self.watched_tickers: Set[str] = set()

    def load_scanner_results(self, scanner_name: str) -> None:
        """Load tickers matched by today's scanner."""
        today = datetime.utcnow().date()
        results = (
            self.db.query(ScannerResult)
            .options(joinedload(ScannerResult.stock))
            .filter(
                ScannerResult.scanner_name == scanner_name,
                ScannerResult.matched_at >= today,
            )
            .all()
        )
        self.watched_tickers = {r.stock.symbol for r in results}
        logger.info(f"Loaded {len(self.watched_tickers)} tickers from {scanner_name}")

    def poll_quotes(
        self,
        interval_seconds: int = 5,
        max_iterations: Optional[int] = None,
    ) -> None:
        """Poll realtime quotes for watched tickers; batch all inserts per cycle."""
        iteration = 0

        while True:
            if max_iterations is not None and iteration >= max_iterations:
                break
            iteration += 1

            records_to_add = []

            for ticker in list(self.watched_tickers):
                try:
                    quote = self.provider.get_realtime_quote(ticker)
                    # Use ORM model class directly — not a string literal
                    stock = self.db.query(Stock).filter_by(symbol=ticker).first()
                    if stock:
                        records_to_add.append(
                            RealtimeQuoteModel(
                                stock_id=stock.id,
                                bid=quote.bid,
                                ask=quote.ask,
                                bid_size=quote.bid_size,
                                ask_size=quote.ask_size,
                                last=quote.last,
                                open=quote.open,
                                high=quote.high,
                                low=quote.low,
                                close=quote.close,
                                volume=quote.volume,
                                change=quote.change,
                                change_pct=quote.change_pct,
                                week_52_high=quote.week_52_high,
                                week_52_low=quote.week_52_low,
                                status=quote.status,
                                timestamp=quote.timestamp,
                            )
                        )
                    if self.alert_engine.should_alert(ticker, quote):
                        self.output_handler.emit_alert(
                            Alert(ticker=ticker, reason="target_reached", quote=quote)
                        )
                except Exception as e:
                    logger.error(f"Error polling {ticker}: {e}")

            # Batch commit all records from this poll cycle
            if records_to_add:
                self.db.add_all(records_to_add)
                self.db.commit()

            time.sleep(interval_seconds)
