"""CLI entrypoint: reset the open sweep run for a tag."""

from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger

from app.db import cli_session_scope
from app.errors import NotFoundError
from app.log import configure_cli_logging
from app.repository import TagRepo, TagSweepRepo
from app.services import create_tag_sweep_reset_service

_sweep_repo = TagSweepRepo()
_tag_repo = TagRepo()
_reset_service = create_tag_sweep_reset_service()


async def _run(tag_name: str) -> None:
    async with cli_session_scope() as session:
        tag = await _tag_repo.require_tag_model(session, tag_name)
        run = await _sweep_repo.get_open_sweep(session, tag.id)

        if run is None:
            logger.info("No open sweep run found for tag '{}'.", tag_name)
            return

        batches = await _sweep_repo.get_batches(session, run.id)
        submitted_ids = await _sweep_repo.get_submitted_oracle_ids_for_sweep(session, run.id)

    logger.info("Open run: {}", run.id)
    logger.info("  submitted cards: {}", len(submitted_ids))
    logger.info("  batches: {}", len(batches))
    for b in batches:
        logger.info(
            "    {} — {} cards — {}",
            (b.batch.anthropic_batch_id or "")[:28],
            b.card_count,
            b.batch.status,
        )

    logger.info(
        "Dry run: no rows were deleted. To remove this open run and all linked batches, "
        "run again with --delete (Invoke: sweep.reset --delete)."
    )
    print(run.id, flush=True)


async def _delete(tag_name: str) -> None:
    async with cli_session_scope() as session:
        try:
            result = await _reset_service.delete_open_sweep(session, tag_name)
        except NotFoundError as e:
            logger.error("{}", str(e))
            sys.exit(1)

    if result.deleted_sweep_id is None:
        logger.info("No open sweep run found for tag '{}'.", tag_name)
    else:
        logger.info("Deleted run {} for tag '{}'.", result.deleted_sweep_id, tag_name)


def main() -> None:
    configure_cli_logging()
    parser = argparse.ArgumentParser(
        description=(
            "Inspect the open sweep run for a tag (default). "
            "Pass --delete to remove that run and all linked batches."
        )
    )
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


if __name__ == "__main__":
    main()
