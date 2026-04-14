"""MTGJSON async fetch jobs + per-edition progress rows.

Revision ID: c1a2b3c4d5e6
Revises: f8e9d0c1b2a3
Create Date: 2026-04-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.check_constraints import (
    create_allowed_values_check_constraint,
    drop_allowed_values_check_constraint,
)

revision: str = "c1a2b3c4d5e6"
down_revision: str | None = "f8e9d0c1b2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"
_JOBS = "mtgjson_fetch_jobs"
_EDITIONS = "mtgjson_fetch_job_editions"
_STATE_VALUES = ("requested", "inprogress", "done")


def upgrade() -> None:
    op.create_table(
        _JOBS,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )
    op.create_table(
        _EDITIONS,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "job_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.{_JOBS}.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("set_code", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_cards_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        schema=_SCHEMA,
    )
    create_allowed_values_check_constraint(
        schema=_SCHEMA,
        table=_EDITIONS,
        column="state",
        values=_STATE_VALUES,
    )
    op.create_index(
        f"ix_{_SCHEMA}_{_EDITIONS}_job_id",
        _EDITIONS,
        ["job_id"],
        unique=False,
        schema=_SCHEMA,
    )
    op.create_unique_constraint(
        f"uq_{_SCHEMA}_{_EDITIONS}_job_id_set_code",
        _EDITIONS,
        ["job_id", "set_code"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        f"uq_{_SCHEMA}_{_EDITIONS}_job_id_set_code",
        _EDITIONS,
        schema=_SCHEMA,
        type_="unique",
    )
    op.drop_index(
        f"ix_{_SCHEMA}_{_EDITIONS}_job_id",
        table_name=_EDITIONS,
        schema=_SCHEMA,
    )
    drop_allowed_values_check_constraint(schema=_SCHEMA, table=_EDITIONS, column="state")
    op.drop_table(_EDITIONS, schema=_SCHEMA)
    op.drop_table(_JOBS, schema=_SCHEMA)
