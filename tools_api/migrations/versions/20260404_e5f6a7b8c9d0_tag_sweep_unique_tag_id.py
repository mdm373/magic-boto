"""Enforce 1:1 relationship between tag_sweep and tags.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a9b8c7d6e5f4"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_tag_sweep_tag_id",
        "tag_sweep",
        ["tag_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint("uq_tag_sweep_tag_id", "tag_sweep", schema=_SCHEMA)
