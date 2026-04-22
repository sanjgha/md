"""APScheduler setup for EOD pipeline automation."""

import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


def create_eod_scheduler(eod_callback) -> BlockingScheduler:
    """Schedule EOD pipeline at 4:15 PM ET Monday–Friday."""
    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        eod_callback,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=16,
            minute=15,
            timezone="America/New_York",
        ),
        id="eod_pipeline",
        name="EOD Scanner Pipeline",
        misfire_grace_time=300,
        coalesce=True,
    )
    return scheduler
