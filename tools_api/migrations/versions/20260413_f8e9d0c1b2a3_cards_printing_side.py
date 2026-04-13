"""Add ``cards.side`` (MTGJSON ``a`` / ``b``) + unique ``(scryfall_id, side)``.

Revision ID: f8e9d0c1b2a3
Revises: e3f4a5b6c7d8
Create Date: 2026-04-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.check_constraints import (
    create_allowed_values_check_constraint,
    drop_allowed_values_check_constraint,
)

revision: str = "f8e9d0c1b2a3"
down_revision: str | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"
_TABLE = "cards"
_SIDE_VALUES = ("a", "b")
_UQ_SCRYFALL_SIDE = "uq_cards_scryfall_id_side"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(
            "side",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'a'"),
        ),
        schema=_SCHEMA,
    )
    create_allowed_values_check_constraint(
        schema=_SCHEMA,
        table=_TABLE,
        column="side",
        values=_SIDE_VALUES,
        allow_null=False,
    )
    op.create_index(
        _UQ_SCRYFALL_SIDE,
        _TABLE,
        ["scryfall_id", "side"],
        unique=True,
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(_UQ_SCRYFALL_SIDE, table_name=_TABLE, schema=_SCHEMA)
    drop_allowed_values_check_constraint(
        schema=_SCHEMA,
        table=_TABLE,
        column="side",
    )
    op.drop_column(_TABLE, "side", schema=_SCHEMA)
