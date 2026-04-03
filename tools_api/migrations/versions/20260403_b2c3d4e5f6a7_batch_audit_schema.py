"""Batch audit schema: drop old sweep tables, create batches/tag_sweep/tag_sweep_batches/
tag_sweep_batch_cards/tag_audit.

Data in existing sweep tables is not preserved.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.check_constraints import (
    create_allowed_values_check_constraint,
    drop_allowed_values_check_constraint,
)

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"


def upgrade() -> None:
    # Drop old sweep tables (cascade order: cards → batches → runs).
    op.drop_index(
        "ix_sweep_run_batch_cards_batch_chunk", table_name="sweep_run_batch_cards", schema=_SCHEMA
    )
    op.drop_index(
        "ix_sweep_run_batch_cards_oracle_id", table_name="sweep_run_batch_cards", schema=_SCHEMA
    )
    op.drop_table("sweep_run_batch_cards", schema=_SCHEMA)
    op.drop_table("sweep_run_batches", schema=_SCHEMA)
    op.drop_table("sweep_runs", schema=_SCHEMA)

    # Shared Anthropic batch lifecycle table.
    op.create_table(
        "batches",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("anthropic_batch_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_batches_anthropic_batch_id", "batches", ["anthropic_batch_id"], schema=_SCHEMA
    )
    create_allowed_values_check_constraint(
        schema=_SCHEMA,
        table="batches",
        column="status",
        values=[
            "submitted",
            "in_progress",
            "canceling",
            "ended",
            "processed",
            "errored",
            "expired",
            "canceled",
        ],
    )

    # Tag sweep run (one per tag epoch).
    op.create_table(
        "tag_sweep",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.ForeignKeyConstraint(["tag_id"], ["magic_boto.tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )
    create_allowed_values_check_constraint(
        schema=_SCHEMA,
        table="tag_sweep",
        column="status",
        values=["open", "complete", "failed"],
    )

    # One batch per chunk submitted for a sweep run.
    op.create_table(
        "tag_sweep_batches",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tag_sweep_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("card_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tag_sweep_id"], ["magic_boto.tag_sweep.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["batch_id"], ["magic_boto.batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )

    # One row per oracle_id per chunk.
    op.create_table(
        "tag_sweep_batch_cards",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tag_sweep_batch_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_custom_id", sa.Text(), nullable=False),
        sa.Column("oracle_id", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(
            ["tag_sweep_batch_id"],
            ["magic_boto.tag_sweep_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tag_sweep_batch_id", "chunk_custom_id", "position"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_tag_sweep_batch_cards_oracle_id",
        "tag_sweep_batch_cards",
        ["oracle_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_tag_sweep_batch_cards_batch_chunk",
        "tag_sweep_batch_cards",
        ["tag_sweep_batch_id", "chunk_custom_id"],
        schema=_SCHEMA,
    )

    # Tag audit run (one per audit, 1:1 with a batch).
    op.create_table(
        "tag_audit",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("report", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["tag_id"], ["magic_boto.tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["batch_id"], ["magic_boto.batches.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("tag_audit", schema=_SCHEMA)
    op.drop_index(
        "ix_tag_sweep_batch_cards_batch_chunk", table_name="tag_sweep_batch_cards", schema=_SCHEMA
    )
    op.drop_index(
        "ix_tag_sweep_batch_cards_oracle_id", table_name="tag_sweep_batch_cards", schema=_SCHEMA
    )
    op.drop_table("tag_sweep_batch_cards", schema=_SCHEMA)
    op.drop_table("tag_sweep_batches", schema=_SCHEMA)
    drop_allowed_values_check_constraint(schema=_SCHEMA, table="tag_sweep", column="status")
    op.drop_table("tag_sweep", schema=_SCHEMA)
    drop_allowed_values_check_constraint(schema=_SCHEMA, table="batches", column="status")
    op.drop_index("ix_batches_anthropic_batch_id", table_name="batches", schema=_SCHEMA)
    op.drop_table("batches", schema=_SCHEMA)

    # Recreate old sweep tables (no data restored).
    op.create_table(
        "sweep_runs",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.ForeignKeyConstraint(["tag_id"], ["magic_boto.tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )
    op.create_table(
        "sweep_run_batches",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("card_count", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["magic_boto.sweep_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )
    op.create_table(
        "sweep_run_batch_cards",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sweep_run_batch_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_custom_id", sa.Text(), nullable=False),
        sa.Column("oracle_id", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        "ix_sweep_run_batch_cards_oracle_id", "sweep_run_batch_cards", ["oracle_id"], schema=_SCHEMA
    )
    op.create_index(
        "ix_sweep_run_batch_cards_batch_chunk",
        "sweep_run_batch_cards",
        ["sweep_run_batch_id", "chunk_custom_id"],
        schema=_SCHEMA,
    )
