"""Raise default ``audit_excluded_sample`` on ``tag_audit`` from 40 to 70.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-04-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"


def upgrade() -> None:
    op.alter_column(
        "tag_audit",
        "audit_excluded_sample",
        existing_type=sa.Integer(),
        server_default=sa.text("70"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.alter_column(
        "tag_audit",
        "audit_excluded_sample",
        existing_type=sa.Integer(),
        server_default=sa.text("40"),
        schema=_SCHEMA,
    )
