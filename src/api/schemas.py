"""Pydantic request/response models for the Foundation API."""

from typing import Literal
from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Login request with username and password."""

    username: str
    password: str


class UserOut(BaseModel):
    """User response model."""

    id: int
    username: str

    model_config = {"from_attributes": True}


class SettingsPatch(BaseModel):
    """Keys that may be updated via PUT /api/settings.

    Add fields here when new sub-projects introduce settings.
    """

    theme: Literal["light", "dark"] | None = None
    timezone: str | None = None

    model_config = {"extra": "forbid"}


class SettingsOut(BaseModel):
    """Full settings response returned by GET and PUT /api/settings."""

    theme: str
    timezone: str
