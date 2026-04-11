"""CLI entrypoint: create a tag with a name and description."""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from app.db import cli_session_scope
from app.log import configure_cli_logging
from app.models.card_supertype import CardSupertype
from app.models.card_type import CardType
from app.repository.tag_repo import TagRepo

_tag_repo = TagRepo()


async def _run(
    name: str,
    description: str,
    sweep_include_types: list[str],
    sweep_include_supertypes: list[str],
) -> None:
    async with cli_session_scope() as session:
        existing = await _tag_repo.get_tag(session, name)
        if existing is not None:
            logger.error("Tag '{}' already exists.", name)
            sys.exit(1)
        tag = await _tag_repo.create_tag(
            session,
            name,
            description,
            sweep_include_types=sweep_include_types,
            sweep_include_supertypes=sweep_include_supertypes,
        )
    logger.info("Created tag '{}'.", tag.name)
    if tag.sweep_include_types:
        logger.info("  Types filter: {}", ", ".join(tag.sweep_include_types))
    if tag.sweep_include_supertypes:
        logger.info("  Supertypes filter: {}", ", ".join(tag.sweep_include_supertypes))


def _parse_csv(value: str, all_values: frozenset[str]) -> list[str]:
    """Parse a comma-separated filter string, supporting '-' prefix for exclusion."""
    tokens = [v.strip().lower() for v in value.split(",") if v.strip()]
    if not tokens:
        return []
    negated = [t.startswith("-") for t in tokens]
    if any(negated) and not all(negated):
        mixed = ", ".join(tokens)
        raise ValueError(
            f"Mix of negated and plain values is not allowed: {mixed!r}. "
            "Either prefix all values with '-' to exclude, or provide plain values to include."
        )
    if any(negated):
        return sorted(all_values - {t.lstrip("-") for t in tokens})
    return tokens


def main() -> None:
    configure_cli_logging()
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
            _parse_csv(args.types, frozenset(CardType)),
            _parse_csv(args.supertypes, frozenset(CardSupertype)),
        )
    )


if __name__ == "__main__":
    main()
