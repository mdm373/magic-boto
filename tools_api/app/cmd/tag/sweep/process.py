"""Batch sweep process — apply tags from completed Anthropic batch results."""

from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger

from app.db import sqlalchemy_resources_lifespan
from app.log import configure_cli_logging
from app.services import create_tag_sweep_processor


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply tags from completed batch results for a sweep run."
    )
    parser.add_argument("tag", help="Tag name.")
    parser.add_argument(
        "--include-unsure",
        action="store_true",
        default=False,
        help="Tag uncertain cards with {tag}_unsure.",
    )
    parser.add_argument(
        "--include-excluded",
        action="store_true",
        default=False,
        help="Tag non-qualifying cards with {tag}_excluded.",
    )
    return parser.parse_args()


async def _run(tag: str, include_unsure: bool, include_excluded: bool) -> None:
    async with sqlalchemy_resources_lifespan() as r:
        processor = create_tag_sweep_processor()
        async with r.session_scope() as session:
            await processor.run(session, tag, include_unsure, include_excluded)


def main() -> None:
    configure_cli_logging()
    args = _parse_args()
    try:
        asyncio.run(_run(args.tag, args.include_unsure, args.include_excluded))
    except (ValueError, RuntimeError) as e:
        logger.error("{}", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
