"""Add suggestion column to tag_audit.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"


def upgrade() -> None:
    op.add_column(
        "tag_audit",
        sa.Column("suggestion", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("tag_audit", "suggestion", schema=_SCHEMA)
