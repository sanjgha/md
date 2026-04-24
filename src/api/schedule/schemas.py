"""Pydantic schemas for the schedule API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class LastRun(BaseModel):
    """Last execution record for a scheduled job."""

    ran_at: datetime
    result_count: int


class JobResponse(BaseModel):
    """API response representing a scheduled job's current configuration."""

    job_id: str
    name: str
    trigger_type: str = "cron"
    hour: Optional[int] = None
    minute: Optional[int] = None
    interval_seconds: Optional[int] = None
    enabled: bool
    auto_save: bool
    last_run: Optional[LastRun] = None


class JobPatch(BaseModel):
    """Partial update payload for a scheduled job."""

    hour: Optional[int] = None
    minute: Optional[int] = None
    enabled: Optional[bool] = None
    auto_save: Optional[bool] = None

    @field_validator("hour")
    @classmethod
    def validate_hour(cls, v: Optional[int]) -> Optional[int]:
        """Validate hour is in range 0-23."""
        if v is not None and not (0 <= v <= 23):
            raise ValueError("hour must be between 0 and 23")
        return v

    @field_validator("minute")
    @classmethod
    def validate_minute(cls, v: Optional[int]) -> Optional[int]:
        """Validate minute is in range 0-59."""
        if v is not None and not (0 <= v <= 59):
            raise ValueError("minute must be between 0 and 59")
        return v


class RunResponse(BaseModel):
    """Result of a manual job trigger."""

    status: str  # "ok" | "error"
    result_count: int
    detail: Optional[str] = None
