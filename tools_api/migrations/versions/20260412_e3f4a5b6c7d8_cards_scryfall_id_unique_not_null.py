"""``cards.scryfall_id`` NOT NULL + unique index.

Replaces non-unique ``ix_cards_scryfall_id`` with ``uq_cards_scryfall_id``.
Requires no NULL ``scryfall_id`` rows and no duplicate non-null values.

Revision ID: e3f4a5b6c7d8
Revises: f0a1b2c3d4e5
Create Date: 2026-04-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: str | None = "f0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"
_TABLE = "cards"
_OLD_INDEX = "ix_cards_scryfall_id"
_UNIQUE_INDEX = "uq_cards_scryfall_id"


def upgrade() -> None:
    op.drop_index(_OLD_INDEX, table_name=_TABLE, schema=_SCHEMA)
    op.alter_column(
        _TABLE,
        "scryfall_id",
        existing_type=sa.Text(),
        nullable=False,
        schema=_SCHEMA,
    )
    op.create_index(
        _UNIQUE_INDEX,
        _TABLE,
        ["scryfall_id"],
        unique=True,
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(_UNIQUE_INDEX, table_name=_TABLE, schema=_SCHEMA)
    op.alter_column(
        _TABLE,
        "scryfall_id",
        existing_type=sa.Text(),
        nullable=True,
        schema=_SCHEMA,
    )
    op.create_index(
        _OLD_INDEX,
        _TABLE,
        ["scryfall_id"],
        unique=False,
        schema=_SCHEMA,
    )
