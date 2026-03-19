"""Edition lookup service for MTGJSON editions API."""

from collections.abc import Sequence
from typing import Any

from loguru import logger
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MtgjsonEditionModel
from app.schema import EditionsQuery, MtgjsonEdition
from app.services.mapper import EditionMapper


class EditionService:
    """Edition lookup service. Mapper is injected at construction time."""

    def __init__(self, mapper: EditionMapper) -> None:
        self._mapper = mapper

    async def query_editions(
        self,
        session: AsyncSession,
        query: EditionsQuery,
    ) -> Sequence[MtgjsonEdition]:
        """
        List editions by set_code (exact) and/or name (fuzzy).
        Caller must ensure query is not empty.
        """
        filters: list[Any] = []
        if query.set_code is not None:
            filters.append(MtgjsonEditionModel.code == query.set_code.strip())
        if query.name is not None:
            filters.append(MtgjsonEditionModel.name.ilike(f"%{query.name.strip()}%"))
        stmt = select(MtgjsonEditionModel).where(and_(*filters))
        logger.debug("query_editions query: {}", query.model_dump())
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [self._mapper.to_response(ed) for ed in rows]

    async def get_edition(
        self,
        session: AsyncSession,
        set_code: str,
    ) -> MtgjsonEdition | None:
        """Get one edition by set code. Returns None if not found."""
        logger.debug("Edition lookup: get_edition(set_code={})", set_code)
        stmt = select(MtgjsonEditionModel).where(MtgjsonEditionModel.code == set_code.strip())
        result = await session.execute(stmt)
        edition = result.scalars().one_or_none()
        if edition is None:
            return None
        return self._mapper.to_response(edition)
