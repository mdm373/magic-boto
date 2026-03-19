"""create_card_set_fkey

FK: mtgjson.cards.setCode -> mtgjson.sets.code (one set per card printing).

Prerequisites: every non-null cards.setCode must exist in sets.code; sets.code
must be unique (MTGJSON normally has one row per set). Duplicate set codes or
orphan card setCodes will cause upgrade to fail.

Revision ID: fda31380b343
Revises: 6284111dddc4
Create Date: 2026-03-18 18:55:06.126033

"""

from collections.abc import Sequence

from alembic import op

revision: str = "fda31380b343"
down_revision: str | None = "6284111dddc4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('DROP INDEX IF EXISTS mtgjson."idx_sets_code"')
    op.create_unique_constraint(
        "uq_sets_code",
        "sets",
        ["code"],
        schema="mtgjson",
    )
    op.create_foreign_key(
        "fk_cards_set_code",
        "cards",
        "sets",
        ["setCode"],
        ["code"],
        source_schema="mtgjson",
        referent_schema="mtgjson",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_cards_set_code",
        "cards",
        schema="mtgjson",
        type_="foreignkey",
    )
    op.drop_constraint("uq_sets_code", "sets", schema="mtgjson", type_="unique")
    op.create_index(
        "idx_sets_code",
        "sets",
        ["code"],
        schema="mtgjson",
    )
