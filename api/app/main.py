"""FastAPI app: healthcheck and MTGJSON v1 APIs."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from app.db import close_async_engine, close_pool, get_async_engine, get_pool
from app.routers.mtgjson.v1 import cards as mtgjson_v1_cards

# Load .env from repo root (parent of api/)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_REPO_ROOT / ".env")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await get_pool()
    get_async_engine()  # lazy init SQLAlchemy engine
    yield
    await close_async_engine()
    await close_pool()


app: FastAPI = FastAPI(
    title="Magic Boto API",
    description="Tool backend for the LLM; card search and inventory (Phase 2).",
    lifespan=lifespan,
)

app.include_router(mtgjson_v1_cards.router, prefix="/mtgjson/v1")


@app.get("/health")
def health() -> dict[str, str]:
    """Healthcheck."""
    return {"status": "ok"}
