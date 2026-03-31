"""CLI entrypoint: get a tag by name, or list all tags."""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.services import create_tag_service

_tag_service = create_tag_service()


async def _run(name: str | None) -> None:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        if name:
            tag = await _tag_service.get_tag(session, name)
            if tag is None:
                logger.error("Tag '{}' not found.", name)
                sys.exit(1)
            logger.info("{}: {}", tag.name, tag.description)
        else:
            tags = await _tag_service.list_tags(session)
            if not tags:
                logger.info("No tags found.")
            for tag in tags:
                logger.info(tag.name)


def main() -> None:
    configure_cli_logging()
    if len(sys.argv) > 2:
        logger.error("Usage: python -m app.tag.get.main [name]")
        sys.exit(1)
    name = sys.argv[1] if len(sys.argv) == 2 else None
    asyncio.run(_run(name))


if __name__ == "__main__":
    main()
