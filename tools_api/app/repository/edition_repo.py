"""Repository for ``magic_boto.editions``."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models import EditionModel

from .pg_bulk_upsert import orm_columns_dict


class EditionRepo:
    """Pure ORM access for ``magic_boto.editions``."""

    async def select_existing_set_codes(self, session: AsyncSession) -> set[str]:
        """Return all set codes currently in the DB."""
        stmt = select(EditionModel.set_code)
        rows = await session.execute(stmt)
        return {str(code) for (code,) in rows.all() if code}

    async def insert(self, session: AsyncSession, row: EditionModel) -> None:
        """Insert an edition row, ignoring conflicts on ``set_code``."""
        stmt = (
            pg_insert(EditionModel)
            .values(orm_columns_dict(row))
            .on_conflict_do_nothing(index_elements=["set_code"])
        )
        await session.execute(stmt)

    async def search(
        self,
        session: AsyncSession,
        *,
        set_code: str | None = None,
        name: str | None = None,
    ) -> Sequence[EditionModel]:
        """List editions by set_code (exact) and/or name (fuzzy)."""
        filters: list[ColumnElement[bool]] = []
        if set_code is not None:
            filters.append(EditionModel.set_code == set_code.strip())
        if name is not None:
            filters.append(EditionModel.name.ilike(f"%{name.strip()}%"))
        stmt = select(EditionModel).where(and_(*filters))
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_by_set_code(
        self,
        session: AsyncSession,
        set_code: str,
    ) -> EditionModel | None:
        """Return one edition by set code, or None."""
        stmt = select(EditionModel).where(EditionModel.set_code == set_code.strip())
        result = await session.execute(stmt)
        return result.scalars().one_or_none()
