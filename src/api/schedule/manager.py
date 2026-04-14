"""ScheduleManager wraps APScheduler BackgroundScheduler for job management.

This manager provides per-job locking to prevent double-execution and implements
auto-save watchlist functionality for scheduled scanner runs.

IMPORTANT: Single-Worker Constraint
------------------------------------
The FastAPI app MUST run with --workers 1 when using this manager. BackgroundScheduler
is not multiprocessing-safe and the in-memory locks would not work across workers.

If you need to scale horizontally, migrate to a distributed task queue like Celery
with Redis as the backend broker.
"""

import logging
import threading
from typing import Callable, Dict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from src.api.schedule.jobs import run_eod_job, run_pre_close_job
from src.api.watchlists.service import WatchlistService
from src.db.models import ScheduleConfig, ScannerResult, User, WatchlistSymbol

logger = logging.getLogger(__name__)

# Define job types and their display names
JOB_RUN_TYPES: Dict[str, str] = {
    "eod_scan": "eod",
    "pre_close_scan": "pre_close",
}

JOB_DISPLAY_NAMES: Dict[str, str] = {
    "eod_scan": "EOD Scan",
    "pre_close_scan": "Pre-Close Scan",
}


class AlreadyRunningError(Exception):
    """Raised when attempting to run a job that's already executing."""

    pass


class ScheduleManager:
    """Manages APScheduler BackgroundScheduler with job locking and auto-save.

    The manager is started in FastAPI's lifespan handler and provides methods
    for rescheduling, pausing, resuming, and running jobs immediately.
    """

    def __init__(self) -> None:
        """Initialize the manager with internal state.

        Note: The actual BackgroundScheduler is created in start() to allow
        for reading DB config before initialization.
        """
        self._scheduler: BackgroundScheduler | None = None
        self._callbacks: Dict[str, Callable[[Session], int]] = {}
        self._locks: Dict[str, threading.Lock] = {}

    def start(self, db_session: Session) -> None:
        """Start the background scheduler and load jobs from DB config.

        Reads enabled jobs from schedule_config table and registers them
        with APScheduler. Each job gets a dedicated lock for double-execution
        prevention.

        Args:
            db_session: SQLAlchemy Session for reading schedule_config
        """
        if self._scheduler is not None:
            logger.warning("Scheduler already started, skipping")
            return

        self._scheduler = BackgroundScheduler(timezone="America/New_York")

        # Register job callbacks
        self._callbacks["eod_scan"] = run_eod_job
        self._callbacks["pre_close_scan"] = run_pre_close_job
        self._locks["eod_scan"] = threading.Lock()
        self._locks["pre_close_scan"] = threading.Lock()

        # Load ALL jobs from DB (both enabled and disabled)
        configs = db_session.query(ScheduleConfig).all()

        for cfg in configs:
            if cfg.job_id in JOB_RUN_TYPES:
                self._add_job_to_scheduler(cfg)

                # Pause disabled jobs
                if not cfg.enabled:
                    self._scheduler.pause_job(cfg.job_id)

        self._scheduler.start()
        logger.info("ScheduleManager started with %d jobs", len(configs))

    def stop(self) -> None:
        """Stop the background scheduler gracefully.

        Waits for running jobs to complete (max 3 seconds).
        """
        if self._scheduler is None:
            return

        self._scheduler.shutdown(wait=True)
        self._scheduler = None
        logger.info("ScheduleManager stopped")

    def reschedule(self, job_id: str, hour: int, minute: int) -> None:
        """Update the schedule for a job.

        Modifies the job's CronTrigger in the live scheduler. The job will
        continue running with the new schedule immediately.

        Args:
            job_id: Job identifier (e.g., "eod_scan")
            hour: New hour (0-23)
            minute: New minute (0-59)

        Raises:
            ValueError: If job_id not found
        """
        if self._scheduler is None:
            raise RuntimeError("Scheduler not started")

        job = self._scheduler.get_job(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        # Reschedule with new trigger
        self._scheduler.reschedule_job(
            job_id,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=hour,
                minute=minute,
                timezone="America/New_York",
            ),
        )
        logger.info("Rescheduled %s to %02d:%02d", job_id, hour, minute)

    def pause(self, job_id: str) -> None:
        """Pause a scheduled job.

        The job will not fire automatically but can still be run manually
        via run_now().

        Args:
            job_id: Job identifier

        Raises:
            ValueError: If job_id not found
        """
        if self._scheduler is None:
            raise RuntimeError("Scheduler not started")

        job = self._scheduler.get_job(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        self._scheduler.pause_job(job_id)
        logger.info("Paused %s", job_id)

    def resume(self, job_id: str) -> None:
        """Resume a paused scheduled job.

        Restores automatic firing based on the job's CronTrigger.

        Args:
            job_id: Job identifier

        Raises:
            ValueError: If job_id not found
        """
        if self._scheduler is None:
            raise RuntimeError("Scheduler not started")

        job = self._scheduler.get_job(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        self._scheduler.resume_job(job_id)
        logger.info("Resumed %s", job_id)

    def run_now(self, job_id: str, db_session: Session) -> int:
        """Execute a job callback immediately and synchronously.

        Acquires the job's lock to prevent double-execution. Returns the
        number of results from the scanner run.

        Args:
            job_id: Job identifier
            db_session: SQLAlchemy Session for the callback

        Returns:
            Number of matched results from the scanner

        Raises:
            AlreadyRunningError: If the job is already executing
            ValueError: If job_id not found
        """
        if job_id not in self._callbacks:
            raise ValueError(f"Unknown job_id: {job_id}")

        lock = self._locks.get(job_id)
        if lock is None:
            raise RuntimeError(f"Lock not initialized for {job_id}")

        # Non-blocking acquisition
        if not lock.acquire(blocking=False):
            raise AlreadyRunningError(f"Job {job_id} is already running")

        try:
            callback = self._callbacks[job_id]
            result_count = callback(db_session)

            # Auto-save watchlist if configured
            if result_count > 0:
                self._auto_save_watchlist(job_id, result_count, db_session)

            return result_count
        finally:
            lock.release()

    def _add_job_to_scheduler(self, cfg: ScheduleConfig) -> None:
        """Add a job to the scheduler from a DB config.

        Wraps the callback with lock acquisition and auto-save logic.

        Args:
            cfg: ScheduleConfig instance from database
        """
        if self._scheduler is None:
            raise RuntimeError("Scheduler not started")

        callback = self._make_scheduled_callback(cfg.job_id, cfg.auto_save)

        self._scheduler.add_job(
            callback,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=cfg.hour,
                minute=cfg.minute,
                timezone="America/New_York",
            ),
            id=cfg.job_id,
            name=JOB_DISPLAY_NAMES.get(cfg.job_id, cfg.job_id),
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
        )
        logger.info(
            "Added job %s at %02d:%02d (auto_save=%s)",
            cfg.job_id,
            cfg.hour,
            cfg.minute,
            cfg.auto_save,
        )

    def _make_scheduled_callback(self, job_id: str, auto_save: bool) -> Callable[[], None]:
        """Create a scheduled callback wrapper with lock and auto-save.

        The callback creates its own DB session since it runs in a background
        thread. Sessions are not thread-safe in SQLAlchemy.

        Args:
            job_id: Job identifier
            auto_save: Whether to auto-save watchlist on success (ignored; re-read from DB)

        Returns:
            Callable that executes the job with proper locking
        """

        def callback() -> None:
            from src.db.connection import get_session

            lock = self._locks.get(job_id)
            if lock is None:
                logger.error("Lock not found for %s, skipping execution", job_id)
                return

            # Non-blocking acquisition
            if not lock.acquire(blocking=False):
                logger.warning("Job %s is already running, skipping this execution", job_id)
                return

            try:
                # Create DB session for this thread
                with get_session() as db:
                    job_callback = self._callbacks.get(job_id)
                    if job_callback is None:
                        logger.error("Callback not found for %s", job_id)
                        return

                    result_count = job_callback(db)

                    # Re-read auto_save from DB on each execution
                    cfg = db.query(ScheduleConfig).filter(ScheduleConfig.job_id == job_id).first()
                    if cfg and cfg.auto_save and result_count > 0:
                        self._auto_save_watchlist(job_id, result_count, db)

                    logger.info("Scheduled job %s completed: %d results", job_id, result_count)
            except Exception as e:
                logger.exception("Error executing scheduled job %s: %s", job_id, e)
            finally:
                lock.release()

        return callback

    def _auto_save_watchlist(self, job_id: str, result_count: int, db_session: Session) -> None:
        """Auto-save scanner results to a watchlist.

        Creates/updates a watchlist named "{JOB_DISPLAY_NAMES} — {datetime}" with
        the stock symbols from the latest scanner run.

        Args:
            job_id: Job identifier (e.g., "eod_scan")
            result_count: Number of results (for logging)
            db_session: SQLAlchemy Session
        """
        from datetime import datetime

        try:
            # Get the first user (single-user mode)
            user = db_session.query(User).first()
            if not user:
                logger.error("No user found in database, cannot auto-save watchlist")
                return

            # Get the run time for this job (now, rounded to minute)
            ran_at = datetime.now().replace(second=0, microsecond=0)

            # Query scanner results for this run_type and time
            run_type = job_id  # job_id maps to run_type in ScannerResult
            results = (
                db_session.query(ScannerResult)
                .filter(ScannerResult.run_type == run_type)
                .filter(ScannerResult.matched_at >= ran_at)
                .order_by(ScannerResult.matched_at.desc())
                .all()
            )

            if not results:
                logger.info("No scanner results found for %s at %s, skipping auto-save", job_id, ran_at)
                return

            # Format watchlist name: "EOD Scan — Apr 14 16:15"
            watchlist_name = f"{JOB_DISPLAY_NAMES.get(job_id, job_id)} — {ran_at.strftime('%b %d %H:%M')}"

            # Use WatchlistService to create the watchlist
            watchlist_service = WatchlistService(db_session)

            # Check if watchlist already exists
            from src.db.models import Watchlist

            existing = (
                db_session.query(Watchlist)
                .filter(
                    Watchlist.name == watchlist_name,
                    Watchlist.is_auto_generated == True,  # noqa: E712
                )
                .first()
            )

            if existing:
                # Clear existing symbols
                db_session.query(WatchlistSymbol).filter(
                    WatchlistSymbol.watchlist_id == existing.id
                ).delete()
                watchlist_id = existing.id
            else:
                # Create new watchlist using WatchlistService
                watchlist = watchlist_service.create_watchlist(
                    user_id=user.id,
                    name=watchlist_name,
                )
                # Mark as auto-generated
                watchlist.is_auto_generated = True
                db_session.commit()
                watchlist_id = watchlist.id

            # Add symbols using WatchlistService
            from src.db.models import Stock

            for result in results:
                stock = db_session.query(Stock).filter(Stock.id == result.stock_id).first()
                if stock:
                    watchlist_service.add_symbol(
                        watchlist_id=watchlist_id,
                        user_id=user.id,
                        symbol=stock.symbol,
                    )

            db_session.commit()
            logger.info("Auto-saved %d results to watchlist '%s'", result_count, watchlist_name)
        except Exception as e:
            logger.exception("Error auto-saving watchlist for %s: %s", job_id, e)
            db_session.rollback()
            db_session.close()


# Module-level singleton for FastAPI lifespan
schedule_manager = ScheduleManager()
