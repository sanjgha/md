"""Log file output handler: writes scan results and alerts to a log file."""

import logging
import os
from src.scanner.base import ScanResult
from src.output.base import OutputHandler, Alert


class LogFileOutputHandler(OutputHandler):
    """Write scan results and alerts to a log file."""

    def __init__(self, log_file: str = "logs/market_data.log", log_level: str = "INFO"):
        """Initialize file handler and logger."""
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        self.logger = logging.getLogger("market_data.output")
        self.logger.handlers.clear()
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        self.logger.addHandler(handler)
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))

    def emit_scan_result(self, result: ScanResult) -> None:
        """Log scan result."""
        self.logger.info(
            f"SCAN: {result.scanner_name} stock_id={result.stock_id} metadata={result.metadata}"
        )

    def emit_alert(self, alert: Alert) -> None:
        """Log alert."""
        self.logger.warning(f"ALERT: {alert.ticker} {alert.reason} price=${alert.quote.last}")
