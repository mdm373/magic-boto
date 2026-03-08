import httpx
from openapi_pydantic import OpenAPI


class OpenAPISpecFetcher:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._http_client = client

    async def fetch_spec(self) -> OpenAPI:
        response = await self._http_client.get("/openapi.json")
        response.raise_for_status()
        raw_spec = response.json()
        return OpenAPI.model_validate(raw_spec)
