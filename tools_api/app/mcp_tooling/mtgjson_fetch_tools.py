"""MCP tools for MTGJSON catalog fetch."""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from mcp.types import ToolAnnotations
from pydantic import Field

from app.errors import InvalidRequestError
from app.services.mtgjson_fetch.fetch_run import (
    execute_mtgjson_fetch,
    parse_always_refresh_set_codes,
)
from settings import get_settings

from .error_middleware import AppMcp


class MtgJsonFetchToolResult(TypedDict):
    """JSON returned by ``mtgjson_fetch``."""

    status: Literal["ok"]
    sets_downloaded: list[str]


def register_mtgjson_fetch_tools(app_mcp: AppMcp) -> None:
    """Register MTGJSON fetch MCP tools."""

    @app_mcp.tool(
        name="mtgjson_fetch",
        description=(
            "Download and ingest new MTGJSON sets into the catalog. "
            "Optional ``always_refresh_set_codes`` forces a fresh per-set download and "
            "re-imports card rows for those codes even when the edition already exists. "
            "Include ``SLD`` by default (Secret Lair is updated frequently; same idea as "
            "``invoke fetch.all-sets`` with ``bust_sld``). Returns ``sets_downloaded``: set "
            "codes fetched from the network."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def mtgjson_fetch(
        always_refresh_set_codes: Annotated[
            str,
            Field(
                description=(
                    "Comma-separated MTGJSON set codes to always re-download (cache bust) "
                    "and re-import; should normally include ``SLD``. Examples: ``SLD``, "
                    "``SLD,MOM``. Leave empty only if you want no cache bust for listed codes."
                ),
            ),
        ] = "",
    ) -> MtgJsonFetchToolResult:
        try:
            codes = parse_always_refresh_set_codes(always_refresh_set_codes)
        except ValueError as exc:
            raise InvalidRequestError(str(exc)) from exc
        settings = get_settings()
        async with app_mcp.session() as session:
            sets = await execute_mtgjson_fetch(
                session,
                settings=settings,
                always_refresh_set_codes=codes,
            )
        return {"status": "ok", "sets_downloaded": list(sets)}
