from http import HTTPMethod

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

from app.errors import service_unavailable_error

DROPPED_HEADERS = frozenset[str](["host", "content-length"])


class HttpProxy:
    def __init__(self, base_url: str, timeout: float):
        self._base_url = base_url
        self._timeout = timeout

    async def proxy_request(
        self,
        method: str,
        path: str,
        request: Request,
    ) -> JSONResponse:
        """Forward request to the OpenAI proxy (e.g. LM Studio)."""
        url = f"{self._base_url}{path}"

        headers = {k: v for k, v in request.headers.items() if k.lower() not in DROPPED_HEADERS}
        body = await request.body() if method != HTTPMethod.GET else None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.request(
                    method, url, content=body, headers=headers, params=request.query_params
                )
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                raise service_unavailable_error("OpenAI proxy unreachable") from e
        content = response.json() if response.content else {}
        return JSONResponse(status_code=response.status_code, content=content)
