"""MCP edition tool registrations."""

from __future__ import annotations

from app.api_schema import Edition, EditionsQuery
from app.db import get_async_session_factory
from app.errors import NotFoundError
from app.services import EditionQueryValidator, create_edition_service

from .error_middleware import AppMcp

_edition_service = create_edition_service()
_edition_validator = EditionQueryValidator()


def register_editions_tools(app_mcp: AppMcp) -> None:
    """Register edition MCP tools."""

    @app_mcp.tool(
        name="list_editions",
        description="List MTG editions (sets); filter by exact set_code and/or fuzzy name.",
    )
    async def list_editions(query: EditionsQuery) -> list[Edition]:
        query = _edition_validator.validate_edition_query(query)
        factory = get_async_session_factory()
        async with factory() as session:
            editions = await _edition_service.query_editions(session, query)
            return list(editions)

    @app_mcp.tool(
        name="get_edition",
        description="Get one edition (set) by set code.",
    )
    async def get_edition(set_code: str) -> Edition:
        factory = get_async_session_factory()
        async with factory() as session:
            edition = await _edition_service.get_edition(session, set_code)
            if edition is None:
                raise NotFoundError("Edition not found")
            return edition
