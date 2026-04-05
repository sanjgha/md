"""Composite output handler: fan-out to multiple handlers with exception logging."""

import logging
from typing import List
from src.scanner.base import ScanResult
from src.output.base import OutputHandler, Alert

logger = logging.getLogger(__name__)


class CompositeOutputHandler(OutputHandler):
    """Fan-out to multiple handlers; logs exceptions instead of silently swallowing them."""

    def __init__(self, handlers: List[OutputHandler]):
        """Initialize with list of handlers."""
        self.handlers = handlers

    def emit_scan_result(self, result: ScanResult) -> None:
        """Emit to all handlers; log any exceptions."""
        for handler in self.handlers:
            try:
                handler.emit_scan_result(result)
            except Exception:
                logger.exception(f"{handler.__class__.__name__} failed on emit_scan_result")

    def emit_alert(self, alert: Alert) -> None:
        """Emit alert to all handlers; log any exceptions."""
        for handler in self.handlers:
            try:
                handler.emit_alert(alert)
            except Exception:
                logger.exception(f"{handler.__class__.__name__} failed on emit_alert")
