"""Foundation: users + ui_settings tables with single-user seed.

Revision ID: 20260408_foundation
Revises: a1b2c3d4e5f6
Create Date: 2026-04-08
"""

import os

import sqlalchemy as sa
from alembic import op
from passlib.context import CryptContext
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260408_foundation"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade() -> None:
    """Create users + ui_settings tables and seed the single admin user."""
    username = os.environ.get("APP_USERNAME")
    password = os.environ.get("APP_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "APP_USERNAME and APP_PASSWORD env vars must be set before running this migration."
        )

    users = op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    ui_settings = op.create_table(
        "ui_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key", name="uq_ui_settings_user_key"),
    )

    op.bulk_insert(
        users,
        [{"id": 1, "username": username, "password_hash": _pwd_context.hash(password)}],
    )

    op.bulk_insert(
        ui_settings,
        [
            {"user_id": 1, "key": "theme", "value": "dark"},
            {"user_id": 1, "key": "timezone", "value": "America/New_York"},
        ],
    )


def downgrade() -> None:
    """Drop ui_settings and users tables."""
    op.drop_table("ui_settings")
    op.drop_table("users")
