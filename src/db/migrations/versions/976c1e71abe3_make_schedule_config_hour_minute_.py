"""make_schedule_config_hour_minute_nullable."""

Revision ID: 976c1e71abe3
Revises: 2e59203aa215
Create Date: 2026-04-23 18:27:34.643110

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "976c1e71abe3"
down_revision: Union[str, Sequence[str], None] = "2e59203aa215"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make hour and minute columns nullable to support interval triggers."""
    # First drop the check constraint since it references these columns
    op.drop_constraint("check_trigger_config", "schedule_config", type_="check")

    # Make hour and minute nullable
    op.alter_column("schedule_config", "hour", nullable=True)
    op.alter_column("schedule_config", "minute", nullable=True)

    # Re-add the check constraint with the updated column definitions
    op.create_check_constraint(
        "check_trigger_config",
        "schedule_config",
        "(trigger_type = 'cron' AND hour IS NOT NULL AND minute IS NOT NULL) OR "
        "(trigger_type = 'interval' AND interval_seconds IS NOT NULL AND interval_seconds > 0)",
    )


def downgrade() -> None:
    """Revert hour and minute back to non-nullable."""
    # Drop the check constraint
    op.drop_constraint("check_trigger_config", "schedule_config", type_="check")

    # Make hour and minute non-nullable again
    op.alter_column("schedule_config", "hour", nullable=False)
    op.alter_column("schedule_config", "minute", nullable=False)

    # Re-add the check constraint
    op.create_check_constraint(
        "check_trigger_config",
        "schedule_config",
        "(trigger_type = 'cron' AND hour IS NOT NULL AND minute IS NOT NULL) OR "
        "(trigger_type = 'interval' AND interval_seconds IS NOT NULL AND interval_seconds > 0)",
    )
