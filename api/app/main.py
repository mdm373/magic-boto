"""FastAPI app: healthcheck and MTGJSON v1 APIs."""

import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from loguru import logger

from app.db import close_async_engine, close_pool, get_async_engine, get_pool
from app.routers.mtgjson.v1 import cards as mtgjson_v1_cards
from app.routers.openapi import v1_router as openapi_v1_router

# Load .env from repo root (parent of api/)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_REPO_ROOT / ".env")

# Configure loguru (LOG_LEVEL=DEBUG to see tool requests)
logger.remove()
_log_fmt = (
    "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "{name}:{function}:{line} - <level>{message}</level>"
)
logger.add(sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO").upper(), format=_log_fmt)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await get_pool()
    get_async_engine()  # lazy init SQLAlchemy engine
    yield
    await close_async_engine()
    await close_pool()


app: FastAPI = FastAPI(
    title="Magic Boto API",
    description=(
        "Single API: agent (OpenAI chat under /openapi/v1/) + tools (cards, deck, rules). "
        "See docs/PROJECT-PLAN.md."
    ),
    lifespan=lifespan,
)

app.include_router(mtgjson_v1_cards.router, prefix="/mtgjson/v1")
app.include_router(openapi_v1_router, prefix="/openapi")


@app.get("/health")
def health() -> dict[str, str]:
    """Healthcheck."""
    return {"status": "ok"}
