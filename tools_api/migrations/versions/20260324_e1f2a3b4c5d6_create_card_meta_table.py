"""create_card_meta_table

One row per card: optional numeric power/toughness for filtering.

Revision ID: e1f2a3b4c5d6
Revises: d4e5f6a7b8ca
Create Date: 2026-03-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d4e5f6a7b8ca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "card_meta",
        sa.Column("card_uuid", sa.String(), nullable=False),
        sa.Column("power_number", sa.Integer(), nullable=True),
        sa.Column("toughness_number", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("card_uuid", name="pk_card_meta"),
        schema="public",
    )
    op.create_foreign_key(
        "fk_card_meta_card_uuid",
        "card_meta",
        "cards",
        ["card_uuid"],
        ["uuid"],
        source_schema="public",
        referent_schema="mtgjson",
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_card_meta_power_number",
        "card_meta",
        ["power_number"],
        schema="public",
    )
    op.create_index(
        "idx_card_meta_toughness_number",
        "card_meta",
        ["toughness_number"],
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_card_meta_toughness_number",
        table_name="card_meta",
        schema="public",
    )
    op.drop_index(
        "idx_card_meta_power_number",
        table_name="card_meta",
        schema="public",
    )
    op.drop_constraint(
        "fk_card_meta_card_uuid",
        "card_meta",
        schema="public",
        type_="foreignkey",
    )
    op.drop_table("card_meta", schema="public")
