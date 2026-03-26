"""Repository for ``magic_boto.card_subtypes``."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from .magic_boto_card_subtype import MagicBotoCardSubtypeModel
from .pg_bulk_upsert import bulk_insert_on_conflict_do_nothing, orm_columns_dict


class MagicBotoCardSubtypeRepository:
    def __init__(self, session: AsyncSession, batch_size: int) -> None:
        self._session = session
        self._batch_size = batch_size

    async def insert_many(self, rows: Sequence[MagicBotoCardSubtypeModel]) -> None:
        await bulk_insert_on_conflict_do_nothing(
            self._session,
            batch_size=self._batch_size,
            model=MagicBotoCardSubtypeModel,
            index_elements=("card_id", "card_subtype"),
            param_rows=[orm_columns_dict(row) for row in rows],
        )
