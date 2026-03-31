"""Add reason column to magic_boto.card_tags.

Revision ID: b1c2d3e4f5a6
Revises: a5b4c3d2e1f0
Create Date: 2026-03-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a5b4c3d2e1f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"


def upgrade() -> None:
    op.add_column(
        "card_tags",
        sa.Column("reason", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("card_tags", "reason", schema=_SCHEMA)
