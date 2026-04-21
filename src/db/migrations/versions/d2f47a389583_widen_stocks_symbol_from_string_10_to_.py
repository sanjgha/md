"""widen stocks.symbol from String(10) to String(16).

Revision ID: d2f47a389583
Revises: 91c41e358910
Create Date: 2026-04-21 07:44:06.662461

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d2f47a389583"
down_revision: Union[str, Sequence[str], None] = "91c41e358910"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "stocks", "symbol", existing_type=sa.String(length=10), type_=sa.String(length=16)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "stocks", "symbol", existing_type=sa.String(length=16), type_=sa.String(length=10)
    )
