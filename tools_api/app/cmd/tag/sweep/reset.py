"""CLI entrypoint: full clean reset of a tag sweep (same as MCP ``clean_reset_tag_sweep``)."""

from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger

from app.db import cli_session_scope
from app.errors import NotFoundError
from app.log import configure_cli_logging
from app.services import create_tag_sweep_reset_service

_reset_service = create_tag_sweep_reset_service()


async def _run(tag_name: str) -> None:
    name = tag_name.strip()
    async with cli_session_scope() as session:
        try:
            result = await _reset_service.clean_reset_for_new_sweep(session, name)
        except NotFoundError as e:
            logger.error("{}", str(e))
            sys.exit(1)

    logger.info("Clean reset for tag '{}'.", name)
    logger.info("  card_tags cleared (main + side): {}", result.cards_cleared)
    logger.info("  sweep batch rows deleted: {}", result.batches_deleted)
    if result.deleted_sweep_id is not None:
        logger.info("  removed open sweep run: {}", result.deleted_sweep_id)
    else:
        logger.info("  removed open sweep run: (none)")


def main() -> None:
    configure_cli_logging()
    parser = argparse.ArgumentParser(
        description=(
            "Full reset before a new sweep: clears card_tags for the tag and its "
            "_unsure/_excluded side tags, deletes those side tag rows, deletes sweep "
            "batch history, resets the sweep epoch, and removes any open sweep run. "
            "Does not remove the main tag or change its description."
        )
    )
    parser.add_argument("tag", help="Tag name (main tag must exist).")
    args = parser.parse_args()
    asyncio.run(_run(args.tag))


if __name__ == "__main__":
    main()
