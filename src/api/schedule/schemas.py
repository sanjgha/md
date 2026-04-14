"""Pydantic schemas for the schedule API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class LastRun(BaseModel):
    ran_at: datetime
    result_count: int


class JobResponse(BaseModel):
    job_id: str
    name: str
    hour: int
    minute: int
    enabled: bool
    auto_save: bool
    last_run: Optional[LastRun] = None


class JobPatch(BaseModel):
    hour: Optional[int] = None
    minute: Optional[int] = None
    enabled: Optional[bool] = None
    auto_save: Optional[bool] = None

    @field_validator("hour")
    @classmethod
    def validate_hour(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (0 <= v <= 23):
            raise ValueError("hour must be between 0 and 23")
        return v

    @field_validator("minute")
    @classmethod
    def validate_minute(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (0 <= v <= 59):
            raise ValueError("minute must be between 0 and 59")
        return v


class RunResponse(BaseModel):
    status: str          # "ok" | "error"
    result_count: int
    detail: Optional[str] = None
