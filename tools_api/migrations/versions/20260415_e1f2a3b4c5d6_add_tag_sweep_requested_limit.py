"""Add requested_limit column to magic_boto.tag_sweep.

Revision ID: e1f2a3b4c5d6
Revises: d6e5f4a3b2c1
Create Date: 2026-04-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d6e5f4a3b2c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"


def upgrade() -> None:
    op.add_column(
        "tag_sweep",
        sa.Column(
            "requested_limit",
            sa.Integer(),
            nullable=True,
        ),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("tag_sweep", "requested_limit", schema=_SCHEMA)
