"""CLI entrypoint: reset the open sweep run for a tag."""

from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.services import create_sweep_run_service, create_tag_service

_sweep_run_service = create_sweep_run_service()
_tag_service = create_tag_service()


async def _run(tag_name: str) -> None:
    session_factory = get_async_session_factory()

    async with session_factory() as session:
        tag = await _tag_service.require_tag_model(session, tag_name)
        run = await _sweep_run_service.get_open_run(session, tag.id)

        if run is None:
            logger.info("No open sweep run found for tag '{}'.", tag_name)
            return

        batches = await _sweep_run_service.get_batches(session, run.id)
        submitted_ids = await _sweep_run_service.get_submitted_oracle_ids_for_run(session, run.id)

    logger.info("Open run: {}", run.id)
    logger.info("  submitted cards: {}", len(submitted_ids))
    logger.info("  batches: {}", len(batches))
    for b in batches:
        logger.info("    {} — {} cards — {}", b.batch_id[:28], b.card_count, b.status)

    print(run.id, flush=True)


def main() -> None:
    configure_cli_logging()
    parser = argparse.ArgumentParser(description="Reset the open sweep run for a tag.")
    parser.add_argument("tag", help="Tag name.")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete the open run (and all its batches). Kickoff will start fresh.",
    )
    args = parser.parse_args()

    if args.delete:
        asyncio.run(_delete(args.tag))
    else:
        asyncio.run(_run(args.tag))


async def _delete(tag_name: str) -> None:
    session_factory = get_async_session_factory()

    async with session_factory() as session:
        tag = await _tag_service.require_tag_model(session, tag_name)
        deleted_id = await _sweep_run_service.delete_open_run(session, tag.id)
        if deleted_id is None:
            logger.info("No open sweep run found for tag '{}'.", tag_name)
            sys.exit(0)
        await session.commit()

    logger.info("Deleted run {} for tag '{}'.", deleted_id, tag_name)


if __name__ == "__main__":
    main()
