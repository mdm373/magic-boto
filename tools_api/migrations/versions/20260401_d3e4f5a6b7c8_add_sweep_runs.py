"""Add sweep_runs and sweep_run_batches tables; drop oracle_tag_sweeps.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.check_constraints import (
    create_allowed_values_check_constraint,
    drop_allowed_values_check_constraint,
)

revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"

_SWEEP_RUN_STATUSES = ("open", "complete", "failed")

_SWEEP_RUN_BATCH_STATUSES = (
    "submitted",
    "in_progress",
    "ended",
    "processed",
    "errored",
    "expired",
    "canceling",
    "canceled",
)


def upgrade() -> None:
    op.create_table(
        "sweep_runs",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("last_submitted_oracle_id", sa.Text(), nullable=True),
        sa.Column("all_cards_queued", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["tag_id"], ["magic_boto.tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )
    create_allowed_values_check_constraint(
        schema=_SCHEMA,
        table="sweep_runs",
        column="status",
        values=_SWEEP_RUN_STATUSES,
        allow_null=False,
    )

    op.create_table(
        "sweep_run_batches",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="submitted"),
        sa.Column("card_count", sa.Integer(), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["magic_boto.sweep_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )
    create_allowed_values_check_constraint(
        schema=_SCHEMA,
        table="sweep_run_batches",
        column="status",
        values=_SWEEP_RUN_BATCH_STATUSES,
        allow_null=False,
    )

    op.drop_table("oracle_tag_sweeps", schema=_SCHEMA)


def downgrade() -> None:
    op.create_table(
        "oracle_tag_sweeps",
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("last_swept_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["tag_id"], ["magic_boto.tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tag_id"),
        schema=_SCHEMA,
    )

    drop_allowed_values_check_constraint(schema=_SCHEMA, table="sweep_run_batches", column="status")
    op.drop_table("sweep_run_batches", schema=_SCHEMA)

    drop_allowed_values_check_constraint(schema=_SCHEMA, table="sweep_runs", column="status")
    op.drop_table("sweep_runs", schema=_SCHEMA)
