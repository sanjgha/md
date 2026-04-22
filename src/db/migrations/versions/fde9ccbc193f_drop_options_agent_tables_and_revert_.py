"""Drop options_agent tables and revert schema changes.

Revision ID: fde9ccbc193f
Revises: 10401f8024b1
Create Date: 2026-04-22 14:38:49.390368

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fde9ccbc193f"
down_revision: Union[str, Sequence[str], None] = "10401f8024b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - drop options_agent tables if they exist."""
    # Get the database inspector to check what exists
    from sqlalchemy import inspect

    # Use batch_alter_table for SQLite compatibility if needed
    inspector = inspect(op.get_bind())
    existing_tables = inspector.get_table_names()

    # Drop options_agent tables if they exist (order matters due to FKs)
    if "regime_snapshots" in existing_tables:
        # Check if FK constraint exists before dropping
        try:
            op.drop_constraint(
                "fk_regime_snapshots_symbol_stocks", "regime_snapshots", type_="foreignkey"
            )
        except Exception:
            pass  # Constraint may not exist
        op.drop_table("regime_snapshots")

    if "options_eod_chains" in existing_tables:
        op.drop_table("options_eod_chains")

    if "ivr_snapshots" in existing_tables:
        op.drop_table("ivr_snapshots")


def downgrade() -> None:
    """Downgrade schema - recreate options_agent tables (for reference only)."""
    # This would recreate all the options_agent tables
    # Kept for reference but should not be used in production
    pass
