"""Add tag_types and tag_supertypes tables (card type/supertype include filters for tag sweeps).

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-03-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.check_constraints import (
    create_allowed_values_check_constraint,
    drop_allowed_values_check_constraint,
)

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
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


def upgrade() -> None:
    op.create_table(
        "tag_types",
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("card_type", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["magic_boto.tags.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tag_id", "card_type"),
        schema=_SCHEMA,
    )
    create_allowed_values_check_constraint(
        schema=_SCHEMA,
        table="tag_types",
        column="card_type",
        values=_STANDARD_CARD_TYPES,
        allow_null=False,
    )
    op.create_table(
        "tag_supertypes",
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("card_supertype", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["magic_boto.tags.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tag_id", "card_supertype"),
        schema=_SCHEMA,
    )
    create_allowed_values_check_constraint(
        schema=_SCHEMA,
        table="tag_supertypes",
        column="card_supertype",
        values=_STANDARD_CARD_SUPERTYPES,
        allow_null=False,
    )


def downgrade() -> None:
    drop_allowed_values_check_constraint(
        schema=_SCHEMA, table="tag_supertypes", column="card_supertype"
    )
    op.drop_table("tag_supertypes", schema=_SCHEMA)
    drop_allowed_values_check_constraint(schema=_SCHEMA, table="tag_types", column="card_type")
    op.drop_table("tag_types", schema=_SCHEMA)
