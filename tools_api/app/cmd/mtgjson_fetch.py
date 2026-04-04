"""Entry point for MTGJSON fetch ingest task."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import get_async_sqlalchemy_url
from app.log import configure_cli_logging
from app.services.mtgjson_fetch.fetch_job import create_mtgjson_fetch_job
from settings import get_settings


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
    configure_cli_logging()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
