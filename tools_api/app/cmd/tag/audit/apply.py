"""Tag audit apply — update tag description from audit suggestion, optionally reset tags."""

from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from app.db import cli_session_scope
from app.log import configure_cli_logging
from app.services import create_tag_audit_apply_service, create_tag_sweep_reset_service

_apply_service = create_tag_audit_apply_service()
_reset_service = create_tag_sweep_reset_service()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply audit suggestion to a tag's description.")
    parser.add_argument("tag", help="Tag name.")
    parser.add_argument(
        "--delete-tagged",
        action="store_true",
        default=False,
        help="Delete all card_tag entries for the tag (and its _unsure / _excluded side tags).",
    )
    parser.add_argument(
        "--delete-side-tags",
        action="store_true",
        default=False,
        help="Delete the _unsure and _excluded side tags entirely.",
    )
    return parser.parse_args()


async def _run(
    tag_name: str,
    *,
    delete_tagged: bool,
    delete_side_tags: bool,
) -> None:
    async with cli_session_scope() as session:
        result = await _apply_service.apply(
            session,
            tag_name,
            delete_tagged=delete_tagged,
            delete_side_tags=delete_side_tags,
        )

    logger.info("Applied audit for '{}': {} card(s) cleared.", tag_name, result.cards_cleared)
    if not delete_tagged:
        return
    async with cli_session_scope() as session:
        sweep_result = await _reset_service.delete_open_sweep(session, tag_name)
        if sweep_result.deleted_sweep_id:
            logger.info(
                "Deleted open sweep {} for '{}'.",
                sweep_result.deleted_sweep_id,
                tag_name,
            )


def main() -> None:
    configure_cli_logging()
    args = _parse_args()
    asyncio.run(
        _run(
            args.tag,
            delete_tagged=args.delete_tagged,
            delete_side_tags=args.delete_side_tags,
        )
    )


if __name__ == "__main__":
    main()
