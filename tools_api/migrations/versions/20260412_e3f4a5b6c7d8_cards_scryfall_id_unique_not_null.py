"""``cards.scryfall_id`` NOT NULL + non-unique btree index.

Drops ``ix_cards_scryfall_id``, sets ``scryfall_id`` NOT NULL, recreates ``ix_cards_scryfall_id``
(non-unique) for lookup performance.

Requires no NULL ``scryfall_id`` rows before upgrade.

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
_INDEX = "ix_cards_scryfall_id"


def upgrade() -> None:
    op.drop_index(_INDEX, table_name=_TABLE, schema=_SCHEMA)
    op.alter_column(
        _TABLE,
        "scryfall_id",
        existing_type=sa.Text(),
        nullable=False,
        schema=_SCHEMA,
    )
    op.create_index(
        _INDEX,
        _TABLE,
        ["scryfall_id"],
        unique=False,
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name=_TABLE, schema=_SCHEMA)
    op.alter_column(
        _TABLE,
        "scryfall_id",
        existing_type=sa.Text(),
        nullable=True,
        schema=_SCHEMA,
    )
    op.create_index(
        _INDEX,
        _TABLE,
        ["scryfall_id"],
        unique=False,
        schema=_SCHEMA,
    )
