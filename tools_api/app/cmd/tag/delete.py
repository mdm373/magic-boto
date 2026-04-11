"""CLI entrypoint: delete a tag by name."""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from app.db import cli_session_scope
from app.errors import NotFoundError
from app.repository.tag_repo import TagRepo

_tag_repo = TagRepo()


async def _run(tag_name: str) -> None:
    async with cli_session_scope() as session:
        deleted = await _tag_repo.delete_tag(session, tag_name)
        if not deleted:
            raise NotFoundError(f"Tag '{tag_name}' not found.")
        for side_tag in (f"{tag_name}_unsure", f"{tag_name}_excluded"):
            if await _tag_repo.delete_tag(session, side_tag):
                logger.info("Deleted side tag '{}'.", side_tag)
    logger.info("Deleted tag '{}'.", tag_name)


def main() -> None:
    if len(sys.argv) != 2:
        logger.error("Usage: python -m app.cmd.tag.delete <tag_name>")
        sys.exit(1)
    asyncio.run(_run(sys.argv[1]))


if __name__ == "__main__":
    main()
