"""Add intraday_res_index.

Revision ID: 10401f8024b1
Revises: 90d8b0586ea4
Create Date: 2026-04-19 02:50:58.486911
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "10401f8024b1"
down_revision: Union[str, Sequence[str], None] = "90d8b0586ea4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite index on intraday_candles for hot query path."""
    op.create_index(
        "ix_intraday_candles_stock_res_ts",
        "intraday_candles",
        ["stock_id", "resolution", "timestamp"],
    )


def downgrade() -> None:
    """Remove the composite index."""
    op.drop_index("ix_intraday_candles_stock_res_ts", table_name="intraday_candles")
