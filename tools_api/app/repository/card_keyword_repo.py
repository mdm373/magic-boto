"""Repository for ``magic_boto.card_keywords``."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CardKeywordModel

from .pg_bulk_upsert import bulk_insert_on_conflict_do_nothing, orm_columns_dict


class CardKeywordRepo:
    """Pure ORM access for ``magic_boto.card_keywords``."""

    async def insert_many(
        self,
        session: AsyncSession,
        rows: Sequence[CardKeywordModel],
        *,
        batch_size: int,
    ) -> None:
        await bulk_insert_on_conflict_do_nothing(
            session,
            batch_size=batch_size,
            model=CardKeywordModel,
            index_elements=("card_id", "card_keyword"),
            param_rows=[orm_columns_dict(row) for row in rows],
        )
