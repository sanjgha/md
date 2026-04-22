"""Drop options_agent tables and revert schema changes.

Revision ID: fde9ccbc193f
Revises: 10401f8024b1
Create Date: 2026-04-22 14:38:49.390368

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fde9ccbc193f"
down_revision: Union[str, Sequence[str], None] = "10401f8024b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - drop options_agent tables and revert schema changes."""
    # Drop foreign key constraint from regime_snapshots if it exists
    try:
        op.drop_constraint(
            "fk_regime_snapshots_symbol_stocks", "regime_snapshots", type_="foreignkey"
        )
    except Exception:
        pass  # Constraint may not exist

    # Drop options_agent tables (order matters due to FKs)
    try:
        op.drop_table("regime_snapshots")
    except Exception:
        pass  # Table may not exist

    try:
        op.drop_table("options_eod_chains")
    except Exception:
        pass  # Table may not exist

    try:
        op.drop_table("ivr_snapshots")
    except Exception:
        pass  # Table may not exist

    # Revert stocks.symbol column width from 16 back to 10
    try:
        op.alter_column(
            "stocks", "symbol", existing_type=sa.String(length=16), type_=sa.String(length=10)
        )
    except Exception:
        pass  # Column may already be String(10)


def downgrade() -> None:
    """Downgrade schema - recreate options_agent tables (for reference only)."""
    # This would recreate all the options_agent tables
    # Kept for reference but should not be used in production
    pass
