"""Add user default language preference

Revision ID: 003
Revises: 002
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "default_language",
            sa.String(length=10),
            nullable=False,
            server_default="en",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "default_language")
