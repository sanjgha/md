"""CLI output handler: prints scan results and alerts to stdout."""

from src.scanner.base import ScanResult
from src.output.base import OutputHandler, Alert


class CLIOutputHandler(OutputHandler):
    """Print scan results and alerts to stdout."""

    def emit_scan_result(self, result: ScanResult) -> None:
        """Print scan result to stdout."""
        print(f"[{result.scanner_name}] stock_id={result.stock_id} metadata={result.metadata}")

    def emit_alert(self, alert: Alert) -> None:
        """Print alert to stdout."""
        print(f"ALERT: {alert.ticker} {alert.reason} @ ${alert.quote.last}")
