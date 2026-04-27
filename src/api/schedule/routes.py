"""FastAPI routes for the schedule API.

All routes require an authenticated session (enforced by _get_user dependency).

Routes:
  GET  /api/schedule/jobs                  — list both jobs with config + last run
  PATCH /api/schedule/jobs/{job_id}        — update hour/minute/enabled/auto_save
  POST /api/schedule/jobs/{job_id}/run     — trigger job immediately
  GET /api/schedule/jobs/history           — 7-day run history
"""

import logging
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.api.schedule.manager import (
    AlreadyRunningError,
    JOB_DISPLAY_NAMES,
    JOB_RUN_TYPES,
    schedule_manager,
)
from src.api.schedule.schemas import JobPatch, JobResponse, LastRun, RunResponse
from src.db.models import ScheduleConfig, ScannerResult, User

logger = logging.getLogger(__name__)

router = APIRouter()

_JOB_IDS = list(JOB_DISPLAY_NAMES.keys())


def _get_user(request: Request, db: Session = Depends(get_db)) -> User:
    return get_current_user(request, db)


def _get_last_run(db: Session, run_type: str) -> LastRun | None:
    """Return the most recent run's ran_at and result_count from scanner_results."""
    from sqlalchemy import func as sqlfunc

    latest_at = (
        db.query(sqlfunc.max(ScannerResult.matched_at))
        .filter(ScannerResult.run_type == run_type)
        .scalar()
    )
    if not latest_at:
        return None

    count = (
        db.query(sqlfunc.count(ScannerResult.id))
        .filter(
            ScannerResult.run_type == run_type,
            func.date(ScannerResult.matched_at) == func.date(latest_at),
        )
        .scalar()
    )
    return LastRun(ran_at=latest_at, result_count=count or 0)


@router.get("", response_model=List[JobResponse])
def list_jobs(
    _user: User = Depends(_get_user),
    db: Session = Depends(get_db),
) -> List[JobResponse]:
    """Return both scheduled jobs with their current config and last run info."""
    jobs = []
    for job_id in _JOB_IDS:
        config = db.query(ScheduleConfig).filter_by(job_id=job_id).first()
        if config is None:
            # Seed defaults if migration hasn't run yet (defensive)
            config = ScheduleConfig(
                job_id=job_id,
                trigger_type="cron",
                hour=16 if job_id == "eod_scan" else 15,
                minute=15 if job_id == "eod_scan" else 45,
                enabled=True,
                auto_save=False,
            )

        run_type = JOB_RUN_TYPES[job_id]
        jobs.append(
            JobResponse(
                job_id=job_id,
                name=JOB_DISPLAY_NAMES[job_id],
                trigger_type=config.trigger_type or "cron",
                hour=config.hour,
                minute=config.minute,
                interval_seconds=config.interval_seconds,
                enabled=config.enabled,
                auto_save=config.auto_save,
                last_run=_get_last_run(db, run_type),
            )
        )
    return jobs


@router.patch("/{job_id}", response_model=JobResponse)
def patch_job(
    job_id: str,
    body: JobPatch,
    _user: User = Depends(_get_user),
    db: Session = Depends(get_db),
) -> JobResponse:
    """Partially update a job's config and apply changes to the live scheduler."""
    if job_id not in _JOB_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")

    config = db.query(ScheduleConfig).filter_by(job_id=job_id).first()
    if config is None:
        raise HTTPException(status_code=404, detail="schedule_config row missing; run migrations")

    # Apply partial update
    if body.hour is not None:
        config.hour = body.hour
    if body.minute is not None:
        config.minute = body.minute
    if body.enabled is not None:
        config.enabled = body.enabled
    if body.auto_save is not None:
        config.auto_save = body.auto_save
    config.updated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(config)
    except Exception:
        db.rollback()
        logger.exception("DB commit failed for PATCH schedule/%s", job_id)
        raise HTTPException(status_code=500, detail="Failed to persist schedule change")

    # Apply to live scheduler (best-effort; DB is source of truth on next restart)
    try:
        if config.hour is not None and config.minute is not None:
            schedule_manager.reschedule(job_id, config.hour, config.minute, db)
        if body.enabled is not None:
            if config.enabled:
                schedule_manager.resume(job_id)
            else:
                schedule_manager.pause(job_id)
    except Exception:
        logger.exception("Live reschedule failed for %s — DB updated, restart to resync", job_id)
        # Do NOT rollback; DB is updated. Scheduler will resync on next restart.

    run_type = JOB_RUN_TYPES[job_id]
    return JobResponse(
        job_id=job_id,
        name=JOB_DISPLAY_NAMES[job_id],
        trigger_type=config.trigger_type or "cron",
        hour=config.hour,
        minute=config.minute,
        interval_seconds=config.interval_seconds,
        enabled=config.enabled,
        auto_save=config.auto_save,
        last_run=_get_last_run(db, run_type),
    )


@router.post("/{job_id}/run", response_model=RunResponse)
def run_job_now(
    job_id: str,
    _user: User = Depends(_get_user),
    db: Session = Depends(get_db),
) -> RunResponse:
    """Trigger a job immediately. Returns result_count. Returns 409 if already running."""
    if job_id not in _JOB_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")

    try:
        result_count = schedule_manager.run_now(job_id, db)
        return RunResponse(status="ok", result_count=result_count)
    except AlreadyRunningError:
        raise HTTPException(status_code=409, detail="Job is already running")
    except Exception:
        logger.exception("run_now failed for %s", job_id)
        return RunResponse(status="error", result_count=0, detail="Scan failed; check logs")


@router.get("/history", response_model=List[dict])
def get_history(
    _user: User = Depends(_get_user),
    db: Session = Depends(get_db),
) -> List[dict]:
    """Return last 7 days of scan runs, grouped by run_type + date, sorted desc."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    rows = (
        db.query(
            ScannerResult.run_type,
            func.date(ScannerResult.matched_at).label("run_date"),
            func.max(ScannerResult.matched_at).label("ran_at"),
            func.count(ScannerResult.id).label("result_count"),
        )
        .filter(ScannerResult.matched_at >= cutoff)
        .group_by(ScannerResult.run_type, func.date(ScannerResult.matched_at))
        .order_by(func.max(ScannerResult.matched_at).desc())
        .all()
    )

    run_type_to_name = {v: k for k, v in JOB_RUN_TYPES.items()}
    return [
        {
            "job_name": JOB_DISPLAY_NAMES[run_type_to_name.get(r.run_type, r.run_type)],
            "ran_at": r.ran_at.isoformat(),
            "result_count": r.result_count,
        }
        for r in rows
    ]
