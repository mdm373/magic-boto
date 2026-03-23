"""create_card_subtype_table

Junction table for MTG card subtypes (free-text).

Similar to `card_types`, but `card_subtype` is not an enum/check-constrained
value because MTGJSON's subtype tokens can vary beyond our fixed set.

Revision ID: a1b2c3d4e5f6
Revises: 9706c2d3c837
Create Date: 2026-03-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "9706c2d3c837"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "card_subtypes",
        sa.Column("card_uuid", sa.String(), nullable=False),
        sa.Column("card_subtype", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("card_uuid", "card_subtype", name="pk_card_subtypes"),
        schema="public",
    )
    op.create_foreign_key(
        "fk_card_subtypes_card_uuid",
        "card_subtypes",
        "cards",
        ["card_uuid"],
        ["uuid"],
        source_schema="public",
        referent_schema="mtgjson",
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_card_subtypes_card_subtype",
        "card_subtypes",
        ["card_subtype"],
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_card_subtypes_card_subtype",
        table_name="card_subtypes",
        schema="public",
    )
    op.drop_constraint(
        "fk_card_subtypes_card_uuid",
        "card_subtypes",
        schema="public",
        type_="foreignkey",
    )
    op.drop_table("card_subtypes", schema="public")
