"""create_card_supertype_table

Junction table for MTG card supertypes (fixed enum-like values).

Supertypes are modeled as a CHECK-constrained set because we only support a
small stable group (e.g. Basic, Legendary, etc.).

Revision ID: b6d1f2a3c4
Revises: a1b2c3d4e5f6
Create Date: 2026-03-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.check_constraints import (
    create_allowed_values_check_constraint,
    drop_allowed_values_check_constraint,
)

revision: str = "b6d1f2a3c4"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STANDARD_CARD_SUPERTYPES = (
    "Basic",
    "Host",
    "Legendary",
    "Ongoing",
    "Snow",
    "World",
)


def upgrade() -> None:
    op.create_table(
        "card_supertypes",
        sa.Column("card_uuid", sa.String(), nullable=False),
        sa.Column("card_supertype", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("card_uuid", "card_supertype", name="pk_card_supertypes"),
        schema="public",
    )
    op.create_foreign_key(
        "fk_card_supertypes_card_uuid",
        "card_supertypes",
        "cards",
        ["card_uuid"],
        ["uuid"],
        source_schema="public",
        referent_schema="mtgjson",
        ondelete="CASCADE",
    )
    create_allowed_values_check_constraint(
        schema="public",
        table="card_supertypes",
        column="card_supertype",
        values=_STANDARD_CARD_SUPERTYPES,
        allow_null=False,
    )


def downgrade() -> None:
    drop_allowed_values_check_constraint(
        schema="public",
        table="card_supertypes",
        column="card_supertype",
    )
    op.drop_constraint(
        "fk_card_supertypes_card_uuid",
        "card_supertypes",
        schema="public",
        type_="foreignkey",
    )
    op.drop_table("card_supertypes", schema="public")
