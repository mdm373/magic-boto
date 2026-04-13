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
            "Download and ingest new MTGJSON sets into the catalog"
            "Optional ``always_refresh_set_codes`` re-imports provided set codes always"
            "Returns ``sets_downloaded``: set codes that where imported"
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
                    "Optional comma-separated MTGJSON set codes to always re-download "
                    "(cache bust), e.g. ``SLD,MOM``. Empty means use cache when present."
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
