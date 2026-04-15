"""Add ``updated_at`` column to magic_boto.cards.

Revision ID: d6e5f4a3b2c1
Revises: c1a2b3c4d5e6
Create Date: 2026-04-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6e5f4a3b2c1"
down_revision: str | None = "c1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"


def upgrade() -> None:
    # Nullable: only set when a conflict-update actually changes card fields.
    op.add_column(
        "cards",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("cards", "updated_at", schema=_SCHEMA)

