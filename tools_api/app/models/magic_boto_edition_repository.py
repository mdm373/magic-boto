"""Repository for ``magic_boto.editions``."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .magic_boto_edition import MagicBotoEditionModel
from .pg_bulk_upsert import orm_columns_dict


class MagicBotoEditionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def select_existing_set_codes(self) -> set[str]:
        stmt = select(MagicBotoEditionModel.set_code)
        rows = await self._session.execute(stmt)
        return {str(code) for (code,) in rows.all() if code}

    async def insert(self, row: MagicBotoEditionModel) -> None:
        stmt = (
            pg_insert(MagicBotoEditionModel)
            .values(orm_columns_dict(row))
            .on_conflict_do_nothing(index_elements=["set_code"])
        )
        await self._session.execute(stmt)
