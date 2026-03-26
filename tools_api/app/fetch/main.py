"""Entry point for MTGJSON fetch ingest task."""

from __future__ import annotations

import asyncio
import os
import sys

from loguru import logger
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import get_async_sqlalchemy_url
from settings import get_settings

from .mtgjson_fetch_job import create_mtgjson_fetch_job


def _configure_fetch_logging() -> None:
    """stderr + plain messages: avoids block-buffered stdout under ``uv run`` / IDEs."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="{message}",
    )


async def _run() -> None:
    settings = get_settings()
    engine = create_async_engine(get_async_sqlalchemy_url(), pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            job = create_mtgjson_fetch_job(session=session, settings=settings)
            await job.run()
    finally:
        await engine.dispose()


def main() -> None:
    _configure_fetch_logging()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
