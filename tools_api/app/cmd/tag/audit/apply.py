"""Tag audit apply — update tag description from audit suggestion, optionally reset tags."""

from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.models import TagModel
from app.repository import CardTagRepo, TagAuditRepo, TagRepo, TagSweepRepo

_audit_repo = TagAuditRepo()
_tag_repo = TagRepo()
_card_tag_repo = CardTagRepo()
_sweep_repo = TagSweepRepo()


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
    session_factory = get_async_session_factory()

    async with session_factory() as session:
        tag = await _tag_repo.require_tag_model(session, tag_name)
        audit = await _audit_repo.get_latest_for_tag(session, tag.id)

    if audit is None:
        logger.error("No audit found for tag '{}'.", tag_name)
        sys.exit(1)
    if audit.suggestion is None:
        logger.error("Latest audit for '{}' has no suggestion — run audit.process first.", tag_name)
        sys.exit(1)

    logger.info("Applying suggestion for tag '{}':\n{}", tag_name, audit.suggestion)

    async with session_factory() as session:
        updated = await _tag_repo.update_description(session, tag_name, audit.suggestion)
        if not updated:
            logger.error("Tag '{}' not found when trying to update description.", tag_name)
            sys.exit(1)
        logger.info("Updated description for tag '{}'.", tag_name)

        if delete_tagged or delete_side_tags:
            tags_to_clear: list[TagModel] = []

            main_tag = await _tag_repo.get_tag_model(session, tag_name)
            if main_tag is not None and delete_tagged:
                tags_to_clear.append(main_tag)

            if delete_side_tags:
                for suffix in ("_unsure", "_excluded"):
                    side = await _tag_repo.get_tag_model(session, f"{tag_name}{suffix}")
                    if side is not None:
                        tags_to_clear.append(side)

            for t in tags_to_clear:
                count = await _card_tag_repo.delete_all_for_tag(session, t.id)
                logger.info("Cleared {} card_tag entries for '{}'.", count, t.name)

            if delete_side_tags:
                for suffix in ("_unsure", "_excluded"):
                    deleted = await _tag_repo.delete_tag(session, f"{tag_name}{suffix}")
                    if deleted:
                        logger.info("Deleted side tag '{}{}'.", tag_name, suffix)

        if delete_tagged:
            batch_count = await _sweep_repo.delete_sweep_batch_history_for_tag(session, tag.id)
            logger.info("Cleared {} sweep batch(es) for '{}'.", batch_count, tag_name)
            await _sweep_repo.reset_epoch_for_tag(session, tag.id)
            logger.info("Reset sweep epoch for '{}'; all cards eligible on next kickoff.", tag_name)

        await session.commit()


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
