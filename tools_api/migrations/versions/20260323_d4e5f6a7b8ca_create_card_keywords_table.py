"""create_card_keywords_table

Junction table for MTG card keyword abilities (free text, normalized lowercase in app).

Revision ID: d4e5f6a7b8ca
Revises: c7e8f90a1b2d
Create Date: 2026-03-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8ca"
down_revision: str | None = "c7e8f90a1b2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "card_keywords",
        sa.Column("card_uuid", sa.String(), nullable=False),
        sa.Column("card_keyword", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("card_uuid", "card_keyword", name="pk_card_keywords"),
        schema="public",
    )
    op.create_foreign_key(
        "fk_card_keywords_card_uuid",
        "card_keywords",
        "cards",
        ["card_uuid"],
        ["uuid"],
        source_schema="public",
        referent_schema="mtgjson",
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_card_keywords_card_keyword",
        "card_keywords",
        ["card_keyword"],
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_card_keywords_card_keyword",
        table_name="card_keywords",
        schema="public",
    )
    op.drop_constraint(
        "fk_card_keywords_card_uuid",
        "card_keywords",
        schema="public",
        type_="foreignkey",
    )
    op.drop_table("card_keywords", schema="public")
