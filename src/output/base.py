"""Output handler base classes: OutputHandler ABC and Alert dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.data_provider.base import Quote

# ScanResult lives in scanner.base — single source of truth
from src.scanner.base import ScanResult  # noqa: F401 (re-export for convenience)


@dataclass
class Alert:
    """Real-time alert."""

    ticker: str
    reason: str
    quote: Quote
    timestamp: Optional[datetime] = field(default=None)

    def __post_init__(self):
        """Set timestamp to now if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class OutputHandler(ABC):
    """Abstraction for alert/result destinations."""

    @abstractmethod
    def emit_scan_result(self, result: ScanResult) -> None:
        """Emit a scan result."""
        pass

    @abstractmethod
    def emit_alert(self, alert: Alert) -> None:
        """Emit a real-time alert."""
        pass
