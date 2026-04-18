"""MCP inventory tool registrations."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, TypedDict

from loguru import logger
from mcp.types import ToolAnnotations
from pydantic import Field

from app.errors import InvalidRequestError, NotFoundError
from app.repository import InventoryRepo, canonical_name
from app.services import DEFAULT_INVENTORY_NAME, create_inventory_service
from app.services.inventory_csv_import import (
    import_inventory_from_csv_content,
    import_inventory_from_csv_path,
)
from settings import get_settings

from .error_middleware import AppMcp

_INVENTORY_IMPORT_RESOURCE_URI = "ui://magic-boto/inventory-import"
_UI_DIST = Path(__file__).parent / "ui_dist"
_UI_MIME_TYPE = "text/html;profile=mcp-app"
_FALLBACK_HTML = (
    "<!doctype html><html><body style='font-family:sans-serif;padding:1rem'>"
    "<p>UI not built. Run <code>npm run build</code> inside "
    "<code>tools-ui/</code>.</p></body></html>"
)


def _read_ui(filename: str) -> str:
    path = _UI_DIST / filename
    return path.read_text(encoding="utf-8") if path.exists() else _FALLBACK_HTML


_inventory_service = create_inventory_service()
_inv_repo = InventoryRepo()


class OpenInventoryImportResult(TypedDict):
    """JSON shape returned by ``open_inventory_import``."""

    inventory_name: str
    existing_names: list[str]


class ImportInventoryCsvResult(TypedDict):
    """JSON shape returned by ``import_inventory_csv``."""

    status: Literal["ok"]
    unknown_scryfall_ids: list[str]


def _inventory_name_or_error(raw: str) -> str:
    cn = canonical_name(raw)
    if not cn:
        raise InvalidRequestError("Inventory name is required.")
    if cn == DEFAULT_INVENTORY_NAME:
        raise InvalidRequestError(
            "Cannot modify the reserved inventory _default via MCP; use import for that collection."
        )
    return cn


def register_inventory_tools(app_mcp: AppMcp) -> None:
    """Register inventory MCP tools."""

    @app_mcp.tool(
        name="list_inventory_names",
        description="List inventory (collection) names; use with card search ``inventory_name``.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def list_inventory_names() -> list[str]:
        async with app_mcp.session() as session:
            return await _inv_repo.list_names(session)

    @app_mcp.tool(
        name="create_inventory",
        description=(
            "Get or create a named inventory. Names are trimmed and lowercased; "
            "``_default`` is reserved and cannot be created here."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def create_inventory(
        name: Annotated[
            str,
            Field(description="Collection name (trimmed, stored lowercase)."),
        ],
    ) -> str:
        cn = canonical_name(name)
        if not cn:
            raise InvalidRequestError("Inventory name is required.")
        if cn == DEFAULT_INVENTORY_NAME:
            raise InvalidRequestError(
                "Cannot create the reserved inventory name via MCP; use import for _default."
            )
        async with app_mcp.session() as session:
            inv = await _inv_repo.get_or_create(session, name)
            return inv.name

    @app_mcp.tool(
        name="add_inventory_cards",
        description=(
            "Add copies by Scryfall printing id (one per list element; duplicates add quantity). "
            "``_default`` is not allowed."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def add_inventory_cards(
        inventory_name: Annotated[
            str,
            Field(description="Target inventory (canonical name)."),
        ],
        scryfall_ids: Annotated[
            list[str],
            Field(
                description="Scryfall printing ids (UUID per printing); one copy per element.",
            ),
        ],
    ) -> Literal["ok"]:
        _inventory_name_or_error(inventory_name)
        async with app_mcp.session() as session:
            inv = await _inv_repo.get_by_name(session, inventory_name)
            if inv is None:
                raise NotFoundError("Inventory not found")
            await _inventory_service.add_cards_by_scryfall_ids(session, inv.id, scryfall_ids)
        return "ok"

    @app_mcp.mcp.resource(
        _INVENTORY_IMPORT_RESOURCE_URI,
        name="inventory_import_ui",
        mime_type=_UI_MIME_TYPE,
    )
    def inventory_import_ui() -> str:
        return _read_ui("pages/inventory-import.html")

    @app_mcp.tool(
        name="open_inventory_import",
        description=(
            "Return ``inventory_name`` (optional hint) and ``existing_names`` for CSV import flows."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        meta={"ui": {"resourceUri": _INVENTORY_IMPORT_RESOURCE_URI}},
    )
    async def open_inventory_import(
        inventory_name: Annotated[
            str,
            Field(description="Suggested destination inventory name.", default=""),
        ] = "",
    ) -> OpenInventoryImportResult:
        async with app_mcp.session() as session:
            names = await _inv_repo.list_names(session)
        return {"inventory_name": inventory_name, "existing_names": names}

    @app_mcp.tool(
        name="import_inventory_csv",
        description=(
            "Import UTF-8 CSV from a server path into an inventory. "
            "Requires a Scryfall id column; optional ``count``/``quantity`` (default 1 per row). "
            "Unknown ids are skipped and listed in ``unknown_scryfall_ids`` (server cap applies)."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def import_inventory_csv(
        csv_file_path: Annotated[
            str,
            Field(description="Absolute path to the CSV on the server."),
        ],
        inventory_name: Annotated[
            str,
            Field(description="Target inventory name (new or existing), including _default."),
        ],
    ) -> ImportInventoryCsvResult:
        cn = canonical_name(inventory_name)
        if not cn:
            raise InvalidRequestError("inventory_name is required.")

        raw = csv_file_path.strip()
        if not raw:
            raise InvalidRequestError("csv_file_path is required.")
        csv_path = Path(raw).expanduser().resolve(strict=False)
        if not csv_path.is_file():
            raise InvalidRequestError(f"CSV path is not a readable file: {csv_path}")

        max_unknown = get_settings().inventory_import_max_unknown_scryfall_ids
        async with app_mcp.session() as session:
            ignored = await import_inventory_from_csv_path(session, cn, csv_path)
            if len(ignored) > max_unknown:
                raise InvalidRequestError(
                    f"Too many unknown Scryfall ids ({len(ignored)} > max allowed {max_unknown})."
                )
        for scryfall_id in ignored:
            logger.error(
                "import_inventory_csv: unknown Scryfall id {!r} skipped for {!r}.",
                scryfall_id,
                cn,
            )
        return {"status": "ok", "unknown_scryfall_ids": ignored}

    @app_mcp.tool(
        name="import_inventory_csv_content",
        description=(
            "Import UTF-8 CSV text into an inventory. "
            "Same column rules as ``import_inventory_csv``; unknown ids skipped and reported."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def import_inventory_csv_content(
        csv_content: Annotated[
            str,
            Field(description="Full UTF-8 CSV body."),
        ],
        inventory_name: Annotated[
            str,
            Field(description="Target inventory name (new or existing), including _default."),
        ],
    ) -> ImportInventoryCsvResult:
        cn = canonical_name(inventory_name)
        if not cn:
            raise InvalidRequestError("inventory_name is required.")
        if not csv_content.strip():
            raise InvalidRequestError("csv_content is required.")

        max_unknown = get_settings().inventory_import_max_unknown_scryfall_ids
        async with app_mcp.session() as session:
            ignored = await import_inventory_from_csv_content(session, cn, csv_content)
            if len(ignored) > max_unknown:
                raise InvalidRequestError(
                    f"Too many unknown Scryfall ids ({len(ignored)} > max allowed {max_unknown})."
                )
        for scryfall_id in ignored:
            logger.error(
                "import_inventory_csv_content: unknown Scryfall id {!r} skipped for {!r}.",
                scryfall_id,
                cn,
            )
        return {"status": "ok", "unknown_scryfall_ids": ignored}

    @app_mcp.tool(
        name="remove_inventory_cards",
        description=(
            "Remove copies by Scryfall printing id (one per list element). "
            "Quantities do not go below zero. ``_default`` is not allowed."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def remove_inventory_cards(
        inventory_name: Annotated[
            str,
            Field(description="Target inventory (canonical name)."),
        ],
        scryfall_ids: Annotated[
            list[str],
            Field(
                description="Scryfall printing ids; one copy removed per element.",
            ),
        ],
    ) -> Literal["ok"]:
        _inventory_name_or_error(inventory_name)
        async with app_mcp.session() as session:
            inv = await _inv_repo.get_by_name(session, inventory_name)
            if inv is None:
                raise NotFoundError("Inventory not found")
            await _inventory_service.remove_cards_by_scryfall_ids(session, inv.id, scryfall_ids)
        return "ok"
