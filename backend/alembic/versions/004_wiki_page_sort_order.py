"""Add wiki page sort order

Revision ID: 004
Revises: 003
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wiki_pages",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY tenant_id, category_id
                    ORDER BY created_at, id
                ) - 1 AS rn
            FROM wiki_pages
        )
        UPDATE wiki_pages AS wp
        SET sort_order = ranked.rn
        FROM ranked
        WHERE wp.id = ranked.id
        """
    )

    op.alter_column("wiki_pages", "sort_order", server_default=None)


def downgrade() -> None:
    op.drop_column("wiki_pages", "sort_order")
