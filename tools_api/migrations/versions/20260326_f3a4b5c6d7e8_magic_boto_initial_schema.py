"""magic_boto_initial_schema

Application-owned schema: editions, cards, card_meta (mana value + numeric search
fields), type/supertype/subtype/keyword junctions, and inventory.

Revision ID: f3a4b5c6d7e8
Revises:
Create Date: 2026-03-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.check_constraints import create_allowed_values_check_constraint

revision: str = "f3a4b5c6d7e8"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"

_STANDARD_CARD_TYPES = (
    "artifact",
    "battle",
    "conspiracy",
    "creature",
    "dungeon",
    "enchantment",
    "instant",
    "kindred",
    "land",
    "phenomenon",
    "plane",
    "planeswalker",
    "scheme",
    "sorcery",
    "vanguard",
)

_STANDARD_CARD_SUPERTYPES = (
    "basic",
    "host",
    "legendary",
    "ongoing",
    "snow",
    "world",
)

_RARITY_VALUES = (
    "bonus",
    "common",
    "mythic",
    "rare",
    "special",
    "uncommon",
)

_COUNT_GE_1_CONSTRAINT = "ck_magic_boto_inventory_cards_count_ge_1"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    op.create_table(
        "editions",
        sa.Column("set_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("set_code", name="pk_editions"),
        schema=_SCHEMA,
    )

    op.create_table(
        "cards",
        sa.Column("card_id", sa.Text(), nullable=False),
        sa.Column("oracle_id", sa.Text(), nullable=False),
        sa.Column("set_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("mana_cost", sa.Text(), nullable=True),
        sa.Column("collector_number", sa.Text(), nullable=True),
        sa.Column("type_line", sa.Text(), nullable=True),
        sa.Column("power", sa.Text(), nullable=True),
        sa.Column("toughness", sa.Text(), nullable=True),
        sa.Column("oracle_text", sa.Text(), nullable=True),
        sa.Column("rarity", sa.Text(), nullable=False),
        sa.Column("scryfall_id", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("card_id", name="pk_cards"),
        sa.ForeignKeyConstraint(
            ["set_code"],
            [f"{_SCHEMA}.editions.set_code"],
            name="fk_cards_set_code",
            ondelete="RESTRICT",
        ),
        schema=_SCHEMA,
    )
    create_allowed_values_check_constraint(
        schema=_SCHEMA,
        table="cards",
        column="rarity",
        values=_RARITY_VALUES,
        allow_null=False,
    )
    op.create_index(
        "ix_cards_oracle_id",
        "cards",
        ["oracle_id"],
        unique=False,
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_cards_set_code",
        "cards",
        ["set_code"],
        unique=False,
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_cards_scryfall_id",
        "cards",
        ["scryfall_id"],
        unique=False,
        schema=_SCHEMA,
    )

    op.create_table(
        "card_meta",
        sa.Column("card_id", sa.Text(), nullable=False),
        sa.Column("mana_value", sa.Integer(), nullable=False),
        sa.Column("power_number", sa.Integer(), nullable=True),
        sa.Column("toughness_number", sa.Integer(), nullable=True),
        sa.Column("collector_number", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("card_id", name="pk_card_meta"),
        sa.ForeignKeyConstraint(
            ["card_id"],
            [f"{_SCHEMA}.cards.card_id"],
            name="fk_card_meta_card_id",
            ondelete="CASCADE",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_card_meta_mana_value",
        "card_meta",
        ["mana_value"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_card_meta_power_number",
        "card_meta",
        ["power_number"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_card_meta_toughness_number",
        "card_meta",
        ["toughness_number"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_card_meta_collector_number",
        "card_meta",
        ["collector_number"],
        schema=_SCHEMA,
    )

    op.create_table(
        "card_types",
        sa.Column("card_id", sa.Text(), nullable=False),
        sa.Column("card_type", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("card_id", "card_type", name="pk_card_types"),
        sa.ForeignKeyConstraint(
            ["card_id"],
            [f"{_SCHEMA}.cards.card_id"],
            name="fk_card_types_card_id",
            ondelete="CASCADE",
        ),
        schema=_SCHEMA,
    )
    create_allowed_values_check_constraint(
        schema=_SCHEMA,
        table="card_types",
        column="card_type",
        values=_STANDARD_CARD_TYPES,
        allow_null=False,
    )

    op.create_table(
        "card_supertypes",
        sa.Column("card_id", sa.Text(), nullable=False),
        sa.Column("card_supertype", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("card_id", "card_supertype", name="pk_card_supertypes"),
        sa.ForeignKeyConstraint(
            ["card_id"],
            [f"{_SCHEMA}.cards.card_id"],
            name="fk_card_supertypes_card_id",
            ondelete="CASCADE",
        ),
        schema=_SCHEMA,
    )
    create_allowed_values_check_constraint(
        schema=_SCHEMA,
        table="card_supertypes",
        column="card_supertype",
        values=_STANDARD_CARD_SUPERTYPES,
        allow_null=False,
    )

    op.create_table(
        "card_subtypes",
        sa.Column("card_id", sa.Text(), nullable=False),
        sa.Column("card_subtype", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("card_id", "card_subtype", name="pk_card_subtypes"),
        sa.ForeignKeyConstraint(
            ["card_id"],
            [f"{_SCHEMA}.cards.card_id"],
            name="fk_card_subtypes_card_id",
            ondelete="CASCADE",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_card_subtypes_card_subtype",
        "card_subtypes",
        ["card_subtype"],
        schema=_SCHEMA,
    )

    op.create_table(
        "card_keywords",
        sa.Column("card_id", sa.Text(), nullable=False),
        sa.Column("card_keyword", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("card_id", "card_keyword", name="pk_card_keywords"),
        sa.ForeignKeyConstraint(
            ["card_id"],
            [f"{_SCHEMA}.cards.card_id"],
            name="fk_card_keywords_card_id",
            ondelete="CASCADE",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_card_keywords_card_keyword",
        "card_keywords",
        ["card_keyword"],
        schema=_SCHEMA,
    )

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
        schema=_SCHEMA,
    )
    op.create_table(
        "inventory_cards",
        sa.Column("inventory_id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.Text(), nullable=False),
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
            [f"{_SCHEMA}.inventories.id"],
            name="fk_inventory_cards_inventory",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["card_id"],
            [f"{_SCHEMA}.cards.card_id"],
            name="fk_inventory_cards_card",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "inventory_id",
            "card_id",
            name="pk_inventory_cards",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_inventory_cards_card_id",
        "inventory_cards",
        ["card_id"],
        unique=False,
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
