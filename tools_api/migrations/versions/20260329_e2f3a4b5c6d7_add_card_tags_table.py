"""Add card_tags junction table (card ↔ tag many-to-many).

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-03-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "magic_boto"


def upgrade() -> None:
    op.create_table(
        "card_tags",
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["magic_boto.cards.card_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["magic_boto.tags.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tag_id", "card_id"),
        schema=_SCHEMA,
    )
    op.create_index("ix_card_tags_card_id", "card_tags", ["card_id"], schema=_SCHEMA)
    op.create_index("ix_card_tags_tag_id", "card_tags", ["tag_id"], schema=_SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_card_tags_tag_id", table_name="card_tags", schema=_SCHEMA)
    op.drop_index("ix_card_tags_card_id", table_name="card_tags", schema=_SCHEMA)
    op.drop_table("card_tags", schema=_SCHEMA)
