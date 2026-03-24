"""add_card_meta_collector_number

Numeric collector number for search (parsed from ``mtgjson.cards.number``).

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-03-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "card_meta",
        sa.Column("collector_number", sa.Integer(), nullable=True),
        schema="public",
    )
    op.create_index(
        "idx_card_meta_collector_number",
        "card_meta",
        ["collector_number"],
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_card_meta_collector_number",
        table_name="card_meta",
        schema="public",
    )
    op.drop_column("card_meta", "collector_number", schema="public")
