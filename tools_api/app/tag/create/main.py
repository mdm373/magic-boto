"""CLI entrypoint: create a tag with a name and description."""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.services import create_tag_service

_tag_service = create_tag_service()


async def _run(name: str, description: str) -> None:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        existing = await _tag_service.get_tag(session, name)
        if existing is not None:
            logger.error("Tag '{}' already exists.", name)
            sys.exit(1)
        tag = await _tag_service.create_tag(session, name, description)
        await session.commit()
    logger.info("Created tag '{}'.", tag.name)


def main() -> None:
    configure_cli_logging()
    if len(sys.argv) != 3:
        logger.error("Usage: python -m app.tag.create.main <name> <description>")
        sys.exit(1)
    asyncio.run(_run(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    main()
