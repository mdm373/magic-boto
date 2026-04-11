"""CLI entrypoint: rename a tag (and its _unsure / _excluded side tags)."""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from app.db import cli_session_scope
from app.log import configure_cli_logging
from app.repository.tag_repo import TagRepo

_tag_repo = TagRepo()


async def _run(old_name: str, new_name: str) -> None:
    async with cli_session_scope() as session:
        renamed = await _tag_repo.rename_tag(session, old_name, new_name)
        if not renamed:
            logger.error("Tag '{}' not found.", old_name)
            sys.exit(1)
        for suffix in ("_unsure", "_excluded"):
            old_side = f"{old_name}{suffix}"
            new_side = f"{new_name}{suffix}"
            if await _tag_repo.rename_tag(session, old_side, new_side):
                logger.info("Renamed side tag '{}' → '{}'.", old_side, new_side)
    logger.info("Renamed tag '{}' → '{}'.", old_name, new_name)


def main() -> None:
    configure_cli_logging()
    if len(sys.argv) != 3:
        logger.error("Usage: python -m app.cmd.tag.rename <old_name> <new_name>")
        sys.exit(1)
    asyncio.run(_run(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    main()
