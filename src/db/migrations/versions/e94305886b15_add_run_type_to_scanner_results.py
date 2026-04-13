"""add_run_type_to_scanner_results

Revision ID: e94305886b15
Revises: 1d7173749a9a
Create Date: 2026-04-13 15:45:12.815083

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e94305886b15'
down_revision: Union[str, Sequence[str], None] = '1d7173749a9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Use IF NOT EXISTS to be safe against the column already existing
    # (it may have been added by a prior migration that was removed from version control).
    op.execute(
        "ALTER TABLE scanner_results ADD COLUMN IF NOT EXISTS "
        "run_type VARCHAR(20) NOT NULL DEFAULT 'eod'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('scanner_results', 'run_type')
