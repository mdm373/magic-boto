"""Drop reason column from card_tags.

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-04-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"


def upgrade() -> None:
    op.drop_column("card_tags", "reason", schema=_SCHEMA)


def downgrade() -> None:
    op.add_column(
        "card_tags",
        sa.Column("reason", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )
