"""Redesign sweep pipeline: add sweep_run_batch_cards, drop cursor/queued columns.

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
Create Date: 2026-04-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"


def upgrade() -> None:
    op.create_table(
        "sweep_run_batch_cards",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sweep_run_batch_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_custom_id", sa.Text(), nullable=False),
        sa.Column("oracle_id", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sweep_run_batch_id"],
            ["magic_boto.sweep_run_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sweep_run_batch_id", "chunk_custom_id", "position"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_sweep_run_batch_cards_oracle_id",
        "sweep_run_batch_cards",
        ["oracle_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_sweep_run_batch_cards_batch_chunk",
        "sweep_run_batch_cards",
        ["sweep_run_batch_id", "chunk_custom_id"],
        schema=_SCHEMA,
    )

    op.drop_column("sweep_runs", "last_submitted_oracle_id", schema=_SCHEMA)
    op.drop_column("sweep_runs", "all_cards_queued", schema=_SCHEMA)


def downgrade() -> None:
    op.add_column(
        "sweep_runs",
        sa.Column("all_cards_queued", sa.Boolean(), nullable=False, server_default="false"),
        schema=_SCHEMA,
    )
    op.add_column(
        "sweep_runs",
        sa.Column("last_submitted_oracle_id", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )

    op.drop_index(
        "ix_sweep_run_batch_cards_batch_chunk",
        table_name="sweep_run_batch_cards",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_sweep_run_batch_cards_oracle_id",
        table_name="sweep_run_batch_cards",
        schema=_SCHEMA,
    )
    op.drop_table("sweep_run_batch_cards", schema=_SCHEMA)
