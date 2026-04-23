"""add_interval_trigger_support.

Revision ID: 2e59203aa215
Revises: 5f80eb941e83
Create Date: 2026-04-23

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "2e59203aa215"
down_revision = "5f80eb941e83"
branch_labels = None
depends_on = None


def upgrade():
    """Add interval trigger columns and check constraint."""
    # Add columns
    op.add_column(
        "schedule_config",
        sa.Column("trigger_type", sa.String(10), nullable=False, server_default="cron"),
    )
    op.add_column("schedule_config", sa.Column("interval_seconds", sa.Integer, nullable=True))

    # Add check constraint
    op.create_check_constraint(
        "check_trigger_config",
        "schedule_config",
        "(trigger_type = 'cron' AND hour IS NOT NULL AND minute IS NOT NULL) OR "
        "(trigger_type = 'interval' AND interval_seconds IS NOT NULL AND interval_seconds > 0)",
    )


def downgrade():
    """Remove interval trigger columns and check constraint."""
    op.drop_constraint("check_trigger_config", "schedule_config", type_="check")
    op.drop_column("schedule_config", "interval_seconds")
    op.drop_column("schedule_config", "trigger_type")
