"""CLI entrypoint: create a tag with a name and description."""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.services import create_tag_service

_tag_service = create_tag_service()


async def _run(
    name: str,
    description: str,
    sweep_include_types: list[str],
    sweep_include_supertypes: list[str],
) -> None:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        existing = await _tag_service.get_tag(session, name)
        if existing is not None:
            logger.error("Tag '{}' already exists.", name)
            sys.exit(1)
        tag = await _tag_service.create_tag(
            session,
            name,
            description,
            sweep_include_types=sweep_include_types,
            sweep_include_supertypes=sweep_include_supertypes,
        )
        await session.commit()
    logger.info("Created tag '{}'.", tag.name)
    if tag.sweep_include_types:
        logger.info("  Types filter: {}", ", ".join(tag.sweep_include_types))
    if tag.sweep_include_supertypes:
        logger.info("  Supertypes filter: {}", ", ".join(tag.sweep_include_supertypes))


def _parse_csv(value: str) -> list[str]:
    """Parse a comma-separated string into a stripped, lowercased list, ignoring blanks."""
    return [v.strip().lower() for v in value.split(",") if v.strip()]


def main() -> None:
    configure_cli_logging()
    # argv: name description [--types a,b,...] [--supertypes a,b,...]
    import argparse

    parser = argparse.ArgumentParser(description="Create a tag.")
    parser.add_argument("name", help="Tag name.")
    parser.add_argument("description", help="Tag description.")
    parser.add_argument(
        "--types",
        default="",
        help="Comma-separated card types to restrict the sweep to (e.g. creature,artifact).",
    )
    parser.add_argument(
        "--supertypes",
        default="",
        help="Comma-separated card supertypes to restrict the sweep to (e.g. legendary).",
    )
    args = parser.parse_args()
    asyncio.run(
        _run(
            args.name,
            args.description,
            _parse_csv(args.types),
            _parse_csv(args.supertypes),
        )
    )


if __name__ == "__main__":
    main()
