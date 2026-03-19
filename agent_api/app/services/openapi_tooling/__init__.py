import httpx
from async_lru import alru_cache

from .openapi_tooling import OpenAPITooling
from .path_method_ops import PathMethodOperations
from .spec_fetch import OpenAPISpecFetcher
from .spec_parser import OpenAPISpecParser
from .tool_client import OpenAPIToolClient

_path_method_ops = PathMethodOperations()
_spec_parser = OpenAPISpecParser(_path_method_ops)


async def create_openapi_tooling(timeout: float, base_url: str) -> OpenAPITooling:
    return await _create_cached_openapi_tooling(timeout, base_url)


@alru_cache(maxsize=16)
async def _create_cached_openapi_tooling(timeout: float, base_url: str) -> OpenAPITooling:
    http_client = httpx.AsyncClient(timeout=timeout, base_url=base_url)
    spec_fetcher = OpenAPISpecFetcher(http_client)
    spec = await spec_fetcher.fetch_spec()
    tools = _spec_parser.parse_api_spec_as_tools(spec)
    tool_client = OpenAPIToolClient(_path_method_ops, http_client, spec)
    return OpenAPITooling(tools, tool_client)


__all__ = [
    "create_openapi_tooling",
    "OpenAPITooling",
]
