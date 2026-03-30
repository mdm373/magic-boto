"""Add oracle_tag_sweeps table for per-tag sweep progress tracking.

Revision ID: a5b4c3d2e1f0
Revises: f0e1d2c3b4a5
Create Date: 2026-03-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a5b4c3d2e1f0"
down_revision: str | None = "f0e1d2c3b4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"


def upgrade() -> None:
    op.create_table(
        "oracle_tag_sweeps",
        sa.Column("tag_name", sa.String(), nullable=False),
        sa.Column("last_swept_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tag_name"],
            ["magic_boto.tags.name"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tag_name"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("oracle_tag_sweeps", schema=_SCHEMA)
