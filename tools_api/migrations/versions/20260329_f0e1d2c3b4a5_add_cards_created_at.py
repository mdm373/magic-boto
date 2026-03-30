"""Add created_at column to magic_boto.cards.

Revision ID: f0e1d2c3b4a5
Revises: e2f3a4b5c6d7
Create Date: 2026-03-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f0e1d2c3b4a5"
down_revision: str | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"


def upgrade() -> None:
    op.add_column(
        "cards",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=_SCHEMA,
    )
    # Composite index supports GROUP BY oracle_id + MIN(created_at) in one scan
    op.create_index(
        "ix_cards_oracle_id_created_at",
        "cards",
        ["oracle_id", "created_at"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_cards_oracle_id_created_at", table_name="cards", schema=_SCHEMA)
    op.drop_column("cards", "created_at", schema=_SCHEMA)
