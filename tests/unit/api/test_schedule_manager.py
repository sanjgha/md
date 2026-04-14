"""Unit tests for ScheduleManager."""

import threading
from unittest.mock import MagicMock

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


def _make_manager():
    from src.api.schedule.manager import ScheduleManager
    return ScheduleManager()


def test_run_now_calls_callback_and_returns_count():
    """run_now executes the job callback and returns result_count."""
    manager = _make_manager()
    mock_db = MagicMock()

    # Manually register a fake callback
    manager._callbacks["eod_scan"] = lambda db: 42
    manager._locks["eod_scan"] = threading.Lock()

    count = manager.run_now("eod_scan", mock_db)
    assert count == 42


def test_run_now_raises_when_already_running():
    """run_now raises AlreadyRunningError when the lock is held."""
    from src.api.schedule.manager import AlreadyRunningError

    manager = _make_manager()
    lock = threading.Lock()
    lock.acquire()  # simulate a running job

    manager._callbacks["eod_scan"] = lambda db: 0
    manager._locks["eod_scan"] = lock

    with pytest.raises(AlreadyRunningError):
        manager.run_now("eod_scan", MagicMock())

    lock.release()


def test_reschedule_changes_next_run_time():
    """reschedule updates the job's CronTrigger in the live scheduler."""
    manager = _make_manager()
    scheduler = BackgroundScheduler(timezone="America/New_York")

    def dummy():
        pass

    scheduler.add_job(
        dummy,
        trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=15, timezone="America/New_York"),
        id="eod_scan",
    )
    scheduler.start()
    manager._scheduler = scheduler

    try:
        manager.reschedule("eod_scan", hour=17, minute=30)
        job = scheduler.get_job("eod_scan")
        fields = {f.name: f for f in job.trigger.fields}
        assert str(fields["hour"]) == "17"
        assert str(fields["minute"]) == "30"
    finally:
        scheduler.shutdown(wait=False)


def test_pause_and_resume_job():
    """pause suspends automatic firing; resume restores it."""
    manager = _make_manager()
    scheduler = BackgroundScheduler(timezone="America/New_York")

    def dummy():
        pass

    scheduler.add_job(
        dummy,
        trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=15, timezone="America/New_York"),
        id="eod_scan",
    )
    scheduler.start()
    manager._scheduler = scheduler

    try:
        manager.pause("eod_scan")
        assert scheduler.get_job("eod_scan").next_run_time is None

        manager.resume("eod_scan")
        assert scheduler.get_job("eod_scan").next_run_time is not None
    finally:
        scheduler.shutdown(wait=False)
