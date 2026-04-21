"""Rename IVRSnapshot.current_hv to current_value.

Revision ID: 91c41e358910
Revises: 16f51c6541c6
Create Date: 2026-04-21 07:38:00.622936

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "91c41e358910"
down_revision: Union[str, Sequence[str], None] = "16f51c6541c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("ivr_snapshots", "current_hv", new_column_name="current_value")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("ivr_snapshots", "current_value", new_column_name="current_hv")
