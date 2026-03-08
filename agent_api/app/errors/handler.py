"""Exception handler: convert AppError to JSONResponse."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .app_error import AppError


async def _app_error_handler(_request: object, exc: Exception) -> JSONResponse:
    """Convert raised AppError to JSONResponse."""
    assert isinstance(exc, AppError)
    return JSONResponse(status_code=exc.status_code, content=exc.content)


def register_app_error_handler(app: FastAPI) -> None:
    """Register the AppError exception handler on the app."""
    app.add_exception_handler(AppError, _app_error_handler)
