"""Scanner base classes: Scanner abstract base and ScanResult dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List
from datetime import datetime
from src.scanner.context import ScanContext


@dataclass
class ScanResult:
    """Result from a scanner — single source of truth (not duplicated in output/base.py)."""

    stock_id: int
    scanner_name: str
    metadata: dict
    matched_at: datetime = field(default_factory=datetime.utcnow)


class Scanner(ABC):
    """Abstract base for all scanners."""

    timeframe: str = "daily"
    description: str = ""

    @abstractmethod
    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Run scanner against context, return matches."""
        pass
