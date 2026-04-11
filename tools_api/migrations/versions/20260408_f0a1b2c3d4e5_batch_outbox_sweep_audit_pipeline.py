"""Batch outbox (pending_submit), timestamps, sweep/audit pipeline metadata.

Consolidates 2026-04-08 migrations: nullable ``anthropic_batch_id`` + ``payload``,
``pending_submit`` status, ``created_at`` / nullable ``submitted_at``, ``tag_sweep``
process flags + optional ``post_sweep_audit_id``, ``tag_audit`` sample columns.

Revision ID: f0a1b2c3d4e5
Revises: a9b8c7d6e5f4
Create Date: 2026-04-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.check_constraints import (
    create_allowed_values_check_constraint,
    drop_allowed_values_check_constraint,
)

revision: str = "f0a1b2c3d4e5"
down_revision: str | None = "a9b8c7d6e5f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"

_BATCH_STATUS_VALUES = [
    "pending_submit",
    "submitted",
    "in_progress",
    "canceling",
    "ended",
    "processed",
    "errored",
    "expired",
    "canceled",
]


def upgrade() -> None:
    op.alter_column(
        "batches",
        "anthropic_batch_id",
        existing_type=sa.Text(),
        nullable=True,
        schema=_SCHEMA,
    )
    op.add_column(
        "batches",
        sa.Column("payload", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )

    drop_allowed_values_check_constraint(schema=_SCHEMA, table="batches", column="status")
    op.execute(
        sa.text(
            f"UPDATE \"{_SCHEMA}\".batches SET status = 'pending_submit' "
            "WHERE anthropic_batch_id IS NULL"
        )
    )
    create_allowed_values_check_constraint(
        schema=_SCHEMA,
        table="batches",
        column="status",
        values=_BATCH_STATUS_VALUES,
    )

    op.add_column(
        "batches",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )
    op.alter_column(
        "batches",
        "submitted_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        schema=_SCHEMA,
    )

    op.add_column(
        "tag_sweep",
        sa.Column(
            "pipeline_include_unsure",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        "tag_sweep",
        sa.Column(
            "pipeline_include_excluded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        "tag_sweep",
        sa.Column(
            "post_sweep_audit_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.tag_audit.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        "tag_audit",
        sa.Column(
            "audit_tagged_sample",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("20"),
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        "tag_audit",
        sa.Column(
            "audit_excluded_sample",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("40"),
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        "tag_audit",
        sa.Column(
            "audit_unsure_sample",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("10"),
        ),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("tag_audit", "audit_unsure_sample", schema=_SCHEMA)
    op.drop_column("tag_audit", "audit_excluded_sample", schema=_SCHEMA)
    op.drop_column("tag_audit", "audit_tagged_sample", schema=_SCHEMA)
    op.drop_column("tag_sweep", "post_sweep_audit_id", schema=_SCHEMA)
    op.drop_column("tag_sweep", "pipeline_include_excluded", schema=_SCHEMA)
    op.drop_column("tag_sweep", "pipeline_include_unsure", schema=_SCHEMA)

    op.alter_column(
        "batches",
        "submitted_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        schema=_SCHEMA,
    )
    op.drop_column("batches", "created_at", schema=_SCHEMA)

    drop_allowed_values_check_constraint(schema=_SCHEMA, table="batches", column="status")
    op.execute(
        sa.text(
            f"UPDATE \"{_SCHEMA}\".batches SET status = 'submitted' WHERE status = 'pending_submit'"
        )
    )
    create_allowed_values_check_constraint(
        schema=_SCHEMA,
        table="batches",
        column="status",
        values=[v for v in _BATCH_STATUS_VALUES if v != "pending_submit"],
    )

    op.drop_column("batches", "payload", schema=_SCHEMA)
    op.execute(
        sa.text(
            f"UPDATE \"{_SCHEMA}\".batches SET anthropic_batch_id = '' "
            "WHERE anthropic_batch_id IS NULL"
        )
    )
    op.alter_column(
        "batches",
        "anthropic_batch_id",
        existing_type=sa.Text(),
        nullable=False,
        schema=_SCHEMA,
    )
