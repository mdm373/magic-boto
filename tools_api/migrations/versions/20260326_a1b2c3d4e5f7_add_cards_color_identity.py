"""add_cards_color_identity

Add ``magic_boto.cards.color_identity`` (canonical WUBRG string) + CHECK.

Revision ID: a1b2c3d4e5f7
Revises: f3a4b5c6d7e8
Create Date: 2026-03-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f7"
down_revision: str | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"
_TABLE = "cards"
_COL = "color_identity"
# Only WUBRG pips, at most one of each, canonical order enforced in app (sorted WUBRG).
_CK = f"ck_{_SCHEMA}_{_TABLE}_{_COL}_wubrg"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(_COL, sa.Text(), nullable=False, server_default=""),
        schema=_SCHEMA,
    )
    op.create_check_constraint(
        _CK,
        _TABLE,
        sa.text(f"(\"{_COL}\" ~ '^[WUBRG]{{0,5}}$')"),
        schema=_SCHEMA,
    )
    op.create_index(
        f"ix_{_TABLE}_{_COL}",
        _TABLE,
        [_COL],
        unique=False,
        schema=_SCHEMA,
    )
    op.alter_column(
        _TABLE,
        _COL,
        server_default=None,
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(f"ix_{_TABLE}_{_COL}", table_name=_TABLE, schema=_SCHEMA)
    op.drop_constraint(_CK, _TABLE, schema=_SCHEMA, type_="check")
    op.drop_column(_TABLE, _COL, schema=_SCHEMA)
