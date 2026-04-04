"""Edition lookup service for MTGJSON editions API."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.api_schema import Edition, EditionsQuery
from app.repository import EditionRepo
from app.services.mapper import EditionMapper


class EditionService:
    """Edition lookup service. Mapper is injected at construction time."""

    def __init__(self, mapper: EditionMapper) -> None:
        self._mapper = mapper
        self._repo = EditionRepo()

    async def query_editions(
        self,
        session: AsyncSession,
        query: EditionsQuery,
    ) -> Sequence[Edition]:
        """List editions by set_code (exact) and/or name (fuzzy)."""
        rows = await self._repo.search(session, set_code=query.set_code, name=query.name)
        return [self._mapper.to_response(ed) for ed in rows]

    async def get_edition(
        self,
        session: AsyncSession,
        set_code: str,
    ) -> Edition | None:
        """Get one edition by set code. Returns None if not found."""
        edition = await self._repo.get_by_set_code(session, set_code)
        if edition is None:
            return None
        return self._mapper.to_response(edition)
