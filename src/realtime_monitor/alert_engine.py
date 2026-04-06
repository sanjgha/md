"""Alert engine: manages per-ticker alert rules."""

import logging
from typing import Dict, List
from src.realtime_monitor.rules import AlertRule
from src.data_provider.base import Quote

logger = logging.getLogger(__name__)


class AlertEngine:
    """Manages alert rules for tracked tickers."""

    def __init__(self):
        """Initialize empty rule registry."""
        self.rules: Dict[str, List[AlertRule]] = {}

    def add_rule(self, ticker: str, rule: AlertRule) -> None:
        """Add a rule for a ticker."""
        self.rules.setdefault(ticker, []).append(rule)

    def should_alert(self, ticker: str, quote: Quote) -> bool:
        """Return True if any rule fires for this ticker/quote pair."""
        return any(rule.should_alert(quote) for rule in self.rules.get(ticker, []))

    def clear_rules(self, ticker: str) -> None:
        """Remove all rules for a ticker."""
        self.rules.pop(ticker, None)
