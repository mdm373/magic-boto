"""Repository for ``magic_boto.card_subtypes``."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CardSubtypeModel

from .pg_bulk_upsert import bulk_insert_on_conflict_do_update, orm_columns_dict


class CardSubtypeRepo:
    """Pure ORM access for ``magic_boto.card_subtypes``."""

    async def insert_many(
        self,
        session: AsyncSession,
        rows: Sequence[CardSubtypeModel],
        *,
        batch_size: int,
    ) -> None:
        await bulk_insert_on_conflict_do_update(
            session,
            batch_size=batch_size,
            model=CardSubtypeModel,
            index_elements=("card_id", "card_subtype"),
            param_rows=[orm_columns_dict(row) for row in rows],
        )
