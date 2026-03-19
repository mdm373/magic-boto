"""create_card_type

Revision ID: 9706c2d3c837
Revises: fda31380b343
Create Date: 2026-03-18 21:57:10.039906

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.check_constraints import (
    create_allowed_values_check_constraint,
    drop_allowed_values_check_constraint,
)

# revision identifiers, used by Alembic.
revision: str = "9706c2d3c837"
down_revision: str | None = "fda31380b343"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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


def upgrade() -> None:
    op.create_table(
        "card_types",
        sa.Column("card_uuid", sa.String(), nullable=False),
        sa.Column("card_type", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("card_uuid", "card_type", name="pk_card_types"),
        schema="mtgjson",
    )
    op.create_foreign_key(
        "fk_card_types_card_uuid",
        "card_types",
        "cards",
        ["card_uuid"],
        ["uuid"],
        source_schema="mtgjson",
        referent_schema="mtgjson",
        ondelete="CASCADE",
    )
    create_allowed_values_check_constraint(
        schema="mtgjson",
        table="card_types",
        column="card_type",
        values=_STANDARD_CARD_TYPES,
        allow_null=False,
    )


def downgrade() -> None:
    drop_allowed_values_check_constraint(
        schema="mtgjson",
        table="card_types",
        column="card_type",
    )
    op.drop_constraint(
        "fk_card_types_card_uuid",
        "card_types",
        schema="mtgjson",
        type_="foreignkey",
    )
    op.drop_table("card_types", schema="mtgjson")
