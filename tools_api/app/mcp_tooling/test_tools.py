"""MCP test tool — banana image via MCP UI (ext-apps SEP-1865)."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx
from mcp.types import ImageContent

from app import SERVICE_ROOT

from .error_middleware import AppMcp

# Built by `npm run build` inside tools-ui/. Output lands here via vite.config.ts outDir.
_UI_DIST = Path(__file__).parent / "ui_dist"
_UI_MIME_TYPE = "text/html;profile=mcp-app"

_BANANA_RESOURCE_URI = "ui://magic-boto/banana"
_CARD_RESOURCE_URI = "ui://magic-boto/card"

_IMAGE_CACHE_DIR = SERVICE_ROOT / "cache" / "card_images"
_SCRYFALL_IMAGE_URL = "https://api.scryfall.com/cards/{scryfall_id}?format=image"

_FALLBACK_HTML = (
    "<!doctype html><html><body style='font-family:sans-serif;padding:1rem'>"
    "<p>UI not built. Run <code>npm run build</code> inside "
    "<code>tools-ui/</code>.</p></body></html>"
)


def _read_ui(filename: str) -> str:
    path = _UI_DIST / filename
    return path.read_text(encoding="utf-8") if path.exists() else _FALLBACK_HTML


async def _fetch_card_image(scryfall_id: str) -> bytes:
    """Return image bytes for a Scryfall ID, using the shared cache."""
    cache_path = _IMAGE_CACHE_DIR / f"{scryfall_id}.jpg"
    if cache_path.exists():
        return cache_path.read_bytes()
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(_SCRYFALL_IMAGE_URL.format(scryfall_id=scryfall_id))
    response.raise_for_status()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(response.content)
    return response.content


def register_test_tools(app_mcp: AppMcp) -> None:
    """Register test/diagnostic MCP tools."""

    @app_mcp.mcp.resource(_CARD_RESOURCE_URI, name="card_ui", mime_type=_UI_MIME_TYPE)
    def card_ui() -> str:
        return _read_ui("pages/card.html")

    @app_mcp.tool(
        name="show_card_image",
        description="Renders a Magic card image in the UI by Scryfall ID.",
        meta={"ui": {"resourceUri": _CARD_RESOURCE_URI}},
    )
    async def show_card_image(scryfall_id: str) -> ImageContent:
        image_bytes = await _fetch_card_image(scryfall_id)
        data = base64.standard_b64encode(image_bytes).decode()
        return ImageContent(type="image", data=data, mimeType="image/jpeg")
