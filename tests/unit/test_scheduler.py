"""Unit tests for APScheduler EOD cron setup."""

from unittest.mock import MagicMock
from src.data_fetcher.scheduler import create_eod_scheduler


def test_create_eod_scheduler_returns_scheduler():
    """create_eod_scheduler returns a non-None scheduler."""
    callback = MagicMock()
    scheduler = create_eod_scheduler(callback)
    assert scheduler is not None


def test_scheduler_has_eod_job():
    """Scheduler has exactly one job with id 'eod_pipeline'."""
    callback = MagicMock()
    scheduler = create_eod_scheduler(callback)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "eod_pipeline"


def test_scheduler_job_name():
    """EOD job name is 'EOD Scanner Pipeline'."""
    callback = MagicMock()
    scheduler = create_eod_scheduler(callback)
    assert scheduler.get_jobs()[0].name == "EOD Scanner Pipeline"
