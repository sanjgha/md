"""Unit tests for alert rules."""

from datetime import datetime
from src.realtime_monitor.rules import PriceTargetRule, PercentageGainRule, PercentageLossRule
from src.data_provider.base import Quote


def make_quote(last: float):
    """Create a minimal Quote with the given last price."""
    return Quote(
        timestamp=datetime.now(),
        bid=last - 0.5,
        ask=last + 0.5,
        bid_size=100,
        ask_size=100,
        last=last,
        open=100,
        high=last + 1,
        low=last - 1,
        close=last,
        volume=1000000,
        change=0,
        change_pct=0,
        week_52_high=150,
        week_52_low=80,
        status="active",
    )


def test_price_target_rule_triggers():
    """PriceTargetRule fires when price >= target."""
    rule = PriceTargetRule(target_price=105.0)
    assert rule.should_alert(make_quote(105.2)) is True


def test_price_target_rule_no_trigger():
    """PriceTargetRule does not fire when price < target."""
    rule = PriceTargetRule(target_price=110.0)
    assert rule.should_alert(make_quote(100.2)) is False


def test_percentage_gain_rule_triggers():
    """PercentageGainRule fires when gain >= threshold."""
    rule = PercentageGainRule(entry_price=100.0, gain_pct=5.0)
    assert rule.should_alert(make_quote(106.0)) is True


def test_percentage_gain_rule_no_trigger():
    """PercentageGainRule does not fire when gain < threshold."""
    rule = PercentageGainRule(entry_price=100.0, gain_pct=5.0)
    assert rule.should_alert(make_quote(103.0)) is False


def test_percentage_loss_rule_triggers():
    """PercentageLossRule fires when loss >= threshold."""
    rule = PercentageLossRule(entry_price=100.0, loss_pct=5.0)
    assert rule.should_alert(make_quote(94.0)) is True
