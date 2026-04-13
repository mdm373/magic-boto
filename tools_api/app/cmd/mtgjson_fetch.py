"""Entry point for MTGJSON fetch ingest task."""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import get_async_sqlalchemy_url
from app.log import configure_cli_logging
from app.services.mtgjson_fetch.fetch_run import (
    execute_mtgjson_fetch,
    log_cli_fetch_result,
    parse_always_refresh_set_codes,
)
from settings import get_settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and ingest MTGJSON into the catalog.")
    parser.add_argument(
        "--always-refresh",
        default="",
        metavar="CODES",
        help=(
            "Optional comma-separated set codes whose MTGJSON files are always re-downloaded "
            "(cache bust) and whose cards are re-imported even if the edition already exists. "
            "Omit to use cached per-set JSON when present."
        ),
    )
    return parser.parse_args()


async def _run(*, always_refresh_set_codes: frozenset[str]) -> None:
    settings = get_settings()
    engine = create_async_engine(get_async_sqlalchemy_url(), pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            sets = await execute_mtgjson_fetch(
                session,
                settings=settings,
                always_refresh_set_codes=always_refresh_set_codes,
            )
            log_cli_fetch_result(sets)
    finally:
        await engine.dispose()


def main() -> None:
    configure_cli_logging()
    args = _parse_args()
    try:
        codes = parse_always_refresh_set_codes(args.always_refresh)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    asyncio.run(_run(always_refresh_set_codes=codes))


if __name__ == "__main__":
    main()
