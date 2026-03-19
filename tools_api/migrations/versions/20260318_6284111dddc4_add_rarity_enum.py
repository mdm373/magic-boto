"""add rarity enum

Revision ID: 6284111dddc4
Revises: 002
Create Date: 2026-03-18 18:17:17.015598

"""

from collections.abc import Sequence

from migrations.check_constraints import (
    create_allowed_values_check_constraint,
    drop_allowed_values_check_constraint,
)

# revision identifiers, used by Alembic.
revision: str = "6284111dddc4"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RARITY_VALUES = (
    "rarity",
    "bonus",
    "common",
    "mythic",
    "rare",
    "special",
    "uncommon",
)


def upgrade() -> None:
    create_allowed_values_check_constraint(
        schema="mtgjson",
        table="cards",
        column="rarity",
        values=_RARITY_VALUES,
    )


def downgrade() -> None:
    drop_allowed_values_check_constraint(
        schema="mtgjson",
        table="cards",
        column="rarity",
    )
