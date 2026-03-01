"""Add index on scryfallId for cardIdentifiers (first-class API identifier).

Revision ID: 001
Revises:
Create Date: 2025-02-28

"""

from collections.abc import Sequence

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        'CREATE INDEX IF NOT EXISTS "idx_cardIdentifiers_scryfallId" '
        'ON mtgjson."cardIdentifiers" ("scryfallId")'
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS mtgjson."idx_cardIdentifiers_scryfallId"')
