from collections.abc import Callable, Mapping, Sequence
from http import HTTPMethod

from openapi_pydantic import Operation, PathItem


def _get(path_item: PathItem) -> Operation | None:
    return path_item.get


def _put(path_item: PathItem) -> Operation | None:
    return path_item.put


def _post(path_item: PathItem) -> Operation | None:
    return path_item.post


def _delete(path_item: PathItem) -> Operation | None:
    return path_item.delete


def _patch(path_item: PathItem) -> Operation | None:
    return path_item.patch


_PATH_OPERATIONS: Mapping[HTTPMethod, Callable[[PathItem], Operation | None]] = {
    HTTPMethod.GET: _get,
    HTTPMethod.PUT: _put,
    HTTPMethod.POST: _post,
    HTTPMethod.DELETE: _delete,
    HTTPMethod.PATCH: _patch,
}


class PathMethodOperations:
    def get_path_method_operation(
        self, path_item: PathItem, method: HTTPMethod
    ) -> Operation | None:
        return _PATH_OPERATIONS[method](path_item)

    def supported_methods(self) -> Sequence[HTTPMethod]:
        return list(_PATH_OPERATIONS.keys())

    def is_supported_method(self, method: HTTPMethod) -> bool:
        return method in _PATH_OPERATIONS
