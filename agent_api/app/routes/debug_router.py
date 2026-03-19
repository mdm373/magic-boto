from fastapi import APIRouter

from app.services import create_openapi_tooling
from settings import get_settings

_settings = get_settings()


async def create_debug_router() -> APIRouter:
    router = APIRouter(tags=["debug"])

    tooling = await create_openapi_tooling(
        _settings.tools_api_timeout, _settings.tools_api_base_url
    )
    tools = tooling.get_tools()

    @router.get("/tools", summary="Return all agent tools as JSON (OpenAI function format).")
    def get_tools() -> list[dict[str, object]]:
        return [dict(t) for t in tools]

    return router
