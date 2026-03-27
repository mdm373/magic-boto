"""Add composite inventory_cards index for card search inventory filter.

Revision ID: c9d8e7f6a5b4
Revises: a1b2c3d4e5f7
Create Date: 2026-03-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c9d8e7f6a5b4"
down_revision: str | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"
_INDEX_NAME = "ix_inventory_cards_card_id_inventory_id"


def upgrade() -> None:
    op.create_index(
        _INDEX_NAME,
        "inventory_cards",
        ["card_id", "inventory_id"],
        unique=False,
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="inventory_cards", schema=_SCHEMA)
