"""add_schedule_config

Revision ID: 90d8b0586ea4
Revises: e94305886b15
Create Date: 2026-04-14 12:27:01.604104

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "90d8b0586ea4"
down_revision: Union[str, Sequence[str], None] = "e94305886b15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "schedule_config",
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("auto_save", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.execute("""
        INSERT INTO schedule_config (job_id, hour, minute, enabled, auto_save, updated_at)
        VALUES
            ('eod_scan',       16, 15, true, false, now()),
            ('pre_close_scan', 15, 45, true, false, now())
        ON CONFLICT (job_id) DO NOTHING
        """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("schedule_config")
