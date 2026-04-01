"""Unattended Claude-driven tag sweep — runs directly against the service layer."""

from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.services import create_oracle_tag_sweep_service, create_tag_service
from app.services.oracle_tag_sweep_service import SweepPage
from app.services.tag_service import CardTagEntry
from app.tag.sweep.claude_client import create_sweep_claude_client
from settings import get_settings

_sweep_service = create_oracle_tag_sweep_service()
_tag_service = create_tag_service()
_settings = get_settings()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Claude-driven tag sweep.")
    parser.add_argument("tag", help="Tag name to sweep (must already exist).")
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


async def _run(
    tag_name: str,
    include_unsure: bool,
    include_excluded: bool,
) -> None:
    session_factory = get_async_session_factory()
    unsure_tag_name = f"{tag_name}_unsure"
    excluded_tag_name = f"{tag_name}_excluded"

    # Validate tag exists. Create side-tags only if their feature flag is on.
    async with session_factory() as session:
        tag = await _tag_service.get_tag(session, tag_name)
        if tag is None:
            logger.error("Tag '{}' not found. Create it in Claude Desktop first.", tag_name)
            sys.exit(1)
        if include_unsure and await _tag_service.get_tag(session, unsure_tag_name) is None:
            await _tag_service.create_tag(
                session,
                unsure_tag_name,
                f"Cards flagged for manual review during the '{tag_name}' tag sweep.",
            )
            logger.info("Created tag '{}'.", unsure_tag_name)
        if include_excluded and await _tag_service.get_tag(session, excluded_tag_name) is None:
            await _tag_service.create_tag(
                session,
                excluded_tag_name,
                f"Cards that do not qualify for '{tag_name}', as determined by the tag sweep.",
            )
            logger.info("Created tag '{}'.", excluded_tag_name)
        await session.commit()

    # Build the client after tag description is known; description is baked into
    # the cached system prompt so it must be available at construction time.
    client = create_sweep_claude_client(tag.description)

    page_num = 0
    total_tagged = 0
    total_unsure = 0
    total_excluded = 0

    # First page.
    async with session_factory() as session:
        page: SweepPage = await _sweep_service.resume_sweep(
            session, tag_name, _settings.tag_sweep_limit
        )
        await session.commit()

    processed = page.already_processed

    while not page.is_complete:
        page_num += 1
        current_cards = page.cards
        total_pending = page.total_pending
        tag_entries, unsure_entries = client.call(current_cards)

        classified = {e.oracle_id for e in tag_entries} | {e.oracle_id for e in unsure_entries}
        excluded_entries = [
            CardTagEntry(oracle_id=c.oracle_id)
            for c in current_cards
            if c.oracle_id not in classified
        ]

        # Apply tags and advance cursor in one session so they commit atomically.
        async with session_factory() as session:
            if tag_entries:
                await _tag_service.add_card_tags(session, tag_name, tag_entries)
            if include_unsure and unsure_entries:
                await _tag_service.add_card_tags(session, unsure_tag_name, unsure_entries)
            if include_excluded and excluded_entries:
                await _tag_service.add_card_tags(session, excluded_tag_name, excluded_entries)
            page = await _sweep_service.advance_and_fetch(
                session, tag_name, page.next_cursor, _settings.tag_sweep_limit
            )
            await session.commit()

        total_tagged += len(tag_entries)
        total_unsure += len(unsure_entries)
        total_excluded += len(excluded_entries)
        processed += len(current_cards)

        pct = round(processed / total_pending * 100) if total_pending else 0
        logger.info(
            "Page {page} | tagged: {tagged} | unsure: {unsure} | excluded: {excluded}"
            " | processed: {processed} / {total} ({pct}%)",
            page=page_num,
            tagged=len(tag_entries),
            unsure=len(unsure_entries),
            excluded=len(excluded_entries),
            processed=processed,
            total=total_pending,
            pct=pct,
        )

    logger.info(
        "Done. Total tagged: {} | Total unsure: {} | Total excluded: {}",
        total_tagged,
        total_unsure,
        total_excluded,
    )


def main() -> None:
    configure_cli_logging()
    args = _parse_args()
    asyncio.run(_run(args.tag, args.include_unsure, args.include_excluded))


if __name__ == "__main__":
    main()
