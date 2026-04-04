"""Repository for ``magic_boto.card_meta``."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card_meta_model import CardMetaModel

from .pg_bulk_upsert import bulk_insert_on_conflict_do_nothing, orm_columns_dict


class CardMetaRepo:
    """Pure ORM access for ``magic_boto.card_meta``."""

    async def insert_many(
        self,
        session: AsyncSession,
        rows: Sequence[CardMetaModel],
        *,
        batch_size: int,
    ) -> None:
        await bulk_insert_on_conflict_do_nothing(
            session,
            batch_size=batch_size,
            model=CardMetaModel,
            index_elements=("card_id",),
            param_rows=[orm_columns_dict(row) for row in rows],
        )
