"""OpenAI-compatible API under /openapi/v1/ (models, chat completions)."""

from app.routers.openapi.v1 import router as v1_router

__all__ = ["v1_router"]
