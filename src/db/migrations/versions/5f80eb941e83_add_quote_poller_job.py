"""add_quote_poller_job.

Revision ID: 5f80eb941e83
Revises: fde9ccbc193f
Create Date: 2026-04-22 17:35:09.410660

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "5f80eb941e83"
down_revision: Union[str, Sequence[str], None] = "fde9ccbc193f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        INSERT INTO schedule_config (job_id, enabled, hour, minute, auto_save)
        VALUES ('quote_poller', false, 9, 30, false)
        ON CONFLICT (job_id) DO NOTHING
    """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        DELETE FROM schedule_config WHERE job_id = 'quote_poller'
    """
    )
