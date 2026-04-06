"""add unique constraint to stock_news.

Revision ID: a1b2c3d4e5f6
Revises: df27d5f1133c
Create Date: 2026-04-05 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "df27d5f1133c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add unique constraint on (stock_id, source, publication_date) to stock_news."""
    op.create_unique_constraint(
        "uq_stock_news_stock_src_date",
        "stock_news",
        ["stock_id", "source", "publication_date"],
    )


def downgrade() -> None:
    """Drop unique constraint from stock_news."""
    op.drop_constraint("uq_stock_news_stock_src_date", "stock_news", type_="unique")
