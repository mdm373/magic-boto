"""Add FK from cardIdentifiers.uuid to cards.uuid.

Revision ID: 002
Revises: 001
Create Date: 2025-03-01

"""

from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL requires a UNIQUE or PK on the referenced column(s)
    op.create_index(
        "uq_cards_uuid",
        "cards",
        ["uuid"],
        unique=True,
        schema="mtgjson",
    )
    op.create_foreign_key(
        "fk_cardIdentifiers_card",
        "cardIdentifiers",
        "cards",
        ["uuid"],
        ["uuid"],
        source_schema="mtgjson",
        referent_schema="mtgjson",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_cardIdentifiers_card",
        "cardIdentifiers",
        schema="mtgjson",
        type_="foreignkey",
    )
    op.drop_index("uq_cards_uuid", table_name="cards", schema="mtgjson")
