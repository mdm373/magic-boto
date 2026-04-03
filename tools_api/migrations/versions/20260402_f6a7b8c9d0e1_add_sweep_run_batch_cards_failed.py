"""Add failed column to sweep_run_batch_cards.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"


def upgrade() -> None:
    op.add_column(
        "sweep_run_batch_cards",
        sa.Column("failed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("sweep_run_batch_cards", "failed", schema=_SCHEMA)
