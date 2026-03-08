from openai import AsyncOpenAI

from app.services.openapi_tooling import create_openapi_tooling
from settings import get_settings

from .agent import Agent

_settings = get_settings()


async def create_agent() -> Agent:
    tooling = await create_openapi_tooling(
        _settings.tools_api_timeout, _settings.tools_api_base_url
    )
    client = AsyncOpenAI(
        base_url=f"{_settings.openai_proxy_base_url}/v1",
        api_key="lm-studio",
        timeout=_settings.openai_proxy_timeout,
    )
    return Agent(tooling=tooling, open_api_client=client, max_tool_rounds=_settings.max_tool_rounds)


__all__ = [
    "Agent",
    "create_agent",
]
