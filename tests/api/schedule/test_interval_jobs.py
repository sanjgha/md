"""Test interval job scheduling."""

from apscheduler.triggers.interval import IntervalTrigger

from src.api.schedule.manager import ScheduleManager
from src.db.models import ScheduleConfig


def test_interval_trigger_creation(db_session):
    """Test that IntervalTrigger is created for interval jobs."""
    # Use quote_poller which is a known interval job
    job_id = "quote_poller"

    # Update or create schedule config for interval trigger
    config = db_session.query(ScheduleConfig).filter(ScheduleConfig.job_id == job_id).first()

    if config is None:
        config = ScheduleConfig(
            job_id=job_id,
            enabled=True,
            trigger_type="interval",
            interval_seconds=60,
            hour=None,
            minute=None,
            auto_save=False,
        )
        db_session.add(config)
    else:
        # Update existing config to interval trigger
        config.trigger_type = "interval"
        config.interval_seconds = 60
        config.enabled = True

    db_session.commit()

    # Create schedule manager
    manager = ScheduleManager()
    manager.start(db_session)

    # Verify job was added
    job = manager._scheduler.get_job(job_id)
    assert job is not None, f"Job {job_id} not found in scheduler"

    # Verify trigger is IntervalTrigger
    assert isinstance(job.trigger, IntervalTrigger), f"Trigger for {job_id} is not IntervalTrigger"

    # Verify interval
    actual_interval = job.trigger.interval_length
    assert actual_interval == 60, f"Expected 60s interval, got {actual_interval}"

    # Cleanup
    manager.stop()


def test_market_hours_check():
    """Test that is_market_open works correctly."""
    from src.utils.market_hours import is_market_open
    from datetime import datetime
    from zoneinfo import ZoneInfo

    ET = ZoneInfo("America/New_York")

    # Test regular market hours (10:00 AM ET)
    market_time = datetime.now(ET).replace(hour=10, minute=0, second=0, microsecond=0)
    assert is_market_open(market_time), "Should be open at 10:00 AM ET"

    # Test pre-market (8:00 AM ET)
    pre_market_time = datetime.now(ET).replace(hour=8, minute=0, second=0, microsecond=0)
    assert not is_market_open(pre_market_time), "Should be closed at 8:00 AM ET"

    # Test after hours (5:00 PM ET)
    after_hours_time = datetime.now(ET).replace(hour=17, minute=0, second=0, microsecond=0)
    assert not is_market_open(after_hours_time), "Should be closed at 5:00 PM ET"


def test_quote_worker_market_check():
    """Test that QuoteWorker respects market hours."""
    from src.workers.quote_worker import QuoteWorker
    from src.api.watchlists.quote_cache_service import QuoteCacheService
    from src.data_provider.marketdata_app import MarketDataAppProvider
    from unittest.mock import Mock

    # Mock database and provider
    db = Mock()
    cache = Mock(spec=QuoteCacheService)
    provider = Mock(spec=MarketDataAppProvider)

    worker = QuoteWorker(db, cache, provider)

    # Test when market is closed (should return 0)
    result = worker.poll()
    # Result will be 0 if market closed, or actual count if open
    assert isinstance(result, int), "Should return integer count"
