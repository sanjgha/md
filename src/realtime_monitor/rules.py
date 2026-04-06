"""Alert rules for the realtime monitor."""

from abc import ABC, abstractmethod
from src.data_provider.base import Quote


class AlertRule(ABC):
    """Abstract base for alert rules."""

    @abstractmethod
    def should_alert(self, quote: Quote) -> bool:
        """Return True if alert should fire for this quote."""
        pass


class PriceTargetRule(AlertRule):
    """Alert when price reaches or exceeds target."""

    def __init__(self, target_price: float):
        """Initialize with target price."""
        self.target_price = target_price

    def should_alert(self, quote: Quote) -> bool:
        """Return True when last price >= target."""
        return quote.last >= self.target_price


class PercentageGainRule(AlertRule):
    """Alert when price gains >= gain_pct% from entry."""

    def __init__(self, entry_price: float, gain_pct: float = 5.0):
        """Initialize with entry price and gain threshold."""
        self.entry_price = entry_price
        self.gain_pct = gain_pct

    def should_alert(self, quote: Quote) -> bool:
        """Return True when gain from entry >= threshold."""
        gain = ((quote.last - self.entry_price) / self.entry_price) * 100
        return gain >= self.gain_pct


class PercentageLossRule(AlertRule):
    """Alert when price drops >= loss_pct% from entry."""

    def __init__(self, entry_price: float, loss_pct: float = 5.0):
        """Initialize with entry price and loss threshold."""
        self.entry_price = entry_price
        self.loss_pct = loss_pct

    def should_alert(self, quote: Quote) -> bool:
        """Return True when loss from entry >= threshold."""
        loss = ((self.entry_price - quote.last) / self.entry_price) * 100
        return loss >= self.loss_pct
