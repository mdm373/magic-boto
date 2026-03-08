import json
from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPMethod
from typing import Any

import httpx
from loguru import logger
from openapi_pydantic import OpenAPI, ParameterLocation, PathItem, Reference

from .path_method_ops import PathMethodOperations


class OpenAPIToolClient:
    def __init__(
        self,
        path_method_ops: PathMethodOperations,
        client: httpx.AsyncClient,
        spec: OpenAPI,
    ) -> None:
        self._path_method_ops = path_method_ops
        self._indexed_paths = _index_paths(path_method_ops, spec)
        self._client = client

    async def request_tool(self, operation_id: str, arguments: str) -> str:
        """
        Find the operation in the spec, build the request, call tools_api over HTTP.
        Returns response body as string (for tool content).
        """
        path_info = self._indexed_paths.get(operation_id)
        if path_info is None:
            raise ValueError(f"Unknown operation: {operation_id}")

        try:
            args = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid arguments JSON: {e!s}"})
        if not isinstance(args, dict):
            args = {}
        path = path_info.path_template
        for param in path_info.path_item.parameters or []:
            if isinstance(param, Reference):
                continue
            if param.param_in == ParameterLocation.PATH and param.name in args:
                path = path.replace(f"{{{param.name}}}", str(args.pop(param.name, "")))
        method = path_info.method
        response = await self._request(method, path, args)
        response.raise_for_status()
        body = response.json()
        if isinstance(body, str):
            return body
        return json.dumps(body)

    async def _request(
        self, method: HTTPMethod, path: str, args: Mapping[str, Any]
    ) -> httpx.Response:
        logger.debug(f"Tool request:{method}:{path}")
        if method == HTTPMethod.GET:
            return await self._client.get(path, params=args)
        return await self._client.request(method.value, path, json=args)


@dataclass(frozen=True)
class PathInfo:
    path_template: str
    path_item: PathItem
    method: HTTPMethod


def _index_paths(path_method_ops: PathMethodOperations, spec: OpenAPI) -> Mapping[str, PathInfo]:
    paths = spec.paths or {}
    indexed: dict[str, PathInfo] = {}
    for path_template, path_item in paths.items():
        for method in path_method_ops.supported_methods():
            op = path_method_ops.get_path_method_operation(path_item, method)
            if op is None or not op.operationId:
                continue
            indexed[op.operationId] = PathInfo(
                path_template=path_template, path_item=path_item, method=method
            )
    return indexed
