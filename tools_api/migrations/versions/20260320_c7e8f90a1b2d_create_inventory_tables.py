"""create_inventory_tables

Application-owned inventory: name + junction to mtgjson cards by card UUID
(FK target is mtgjson.cards; API resolves Scryfall printing id / card_id).
Each row is one printing with a quantity column (no duplicate rows per printing).

Revision ID: c7e8f90a1b2d
Revises: b6d1f2a3c4
Create Date: 2026-03-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e8f90a1b2d"
down_revision: str | None = "b6d1f2a3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COUNT_GE_1_CONSTRAINT = "ck_inventory_cards_count_ge_1"


def upgrade() -> None:
    op.create_table(
        "inventories",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_inventories"),
        schema="public",
    )
    op.create_table(
        "inventory_cards",
        sa.Column("inventory_id", sa.Uuid(), nullable=False),
        sa.Column("card_uuid", sa.Text(), nullable=False),
        sa.Column(
            "count",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.CheckConstraint(
            '"count" >= 1',
            name=_COUNT_GE_1_CONSTRAINT,
        ),
        sa.ForeignKeyConstraint(
            ["inventory_id"],
            ["public.inventories.id"],
            name="fk_inventory_cards_inventory",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["card_uuid"],
            ["mtgjson.cards.uuid"],
            name="fk_inventory_cards_card",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "inventory_id",
            "card_uuid",
            name="pk_inventory_cards",
        ),
        schema="public",
    )
    op.create_index(
        "ix_inventory_cards_card_uuid",
        "inventory_cards",
        ["card_uuid"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_cards_card_uuid", table_name="inventory_cards", schema="public")
    op.drop_table("inventory_cards", schema="public")
    op.drop_table("inventories", schema="public")
