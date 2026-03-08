"""OpenAI-style app errors: raise these for centralized handling."""

from http import HTTPStatus
from typing import Any


class AppError(Exception):
    """Exception carrying status_code and JSON content for the response."""

    def __init__(self, status_code: HTTPStatus, content: dict[str, Any]) -> None:
        self.status_code = status_code
        self.content = content
        super().__init__(content.get("error", {}).get("message", "AppError"))


def invalid_request_error(message: str) -> AppError:
    """Raise 400 with type invalid_request_error."""
    return AppError(
        HTTPStatus.BAD_REQUEST,
        {
            "error": {
                "message": message,
                "type": "invalid_request_error",
            },
        },
    )


def service_unavailable_error(message: str) -> AppError:
    """Raise with type service_unavailable."""
    return AppError(
        HTTPStatus.SERVICE_UNAVAILABLE,
        {
            "error": {
                "message": message,
                "type": "service_unavailable",
            },
        },
    )
