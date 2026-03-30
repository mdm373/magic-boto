"""Unattended Claude-driven tag sweep — runs directly against the service layer."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import anthropic
from loguru import logger

from app.db import get_async_session_factory
from app.models.magic_boto_card import MagicBotoCardModel
from app.services import create_oracle_tag_sweep_service, create_tag_service
from app.services.oracle_tag_sweep_service import SweepPage
from settings import get_settings

_sweep_service = create_oracle_tag_sweep_service()
_tag_service = create_tag_service()


def _configure_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="{message}",
    )


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


def _card_to_dict(card: MagicBotoCardModel) -> dict[str, object]:
    return {
        "oracle_id": card.oracle_id,
        "name": card.name,
        "mana_cost": card.mana_cost,
        "type": card.type_line,
        "card_types": [ct.card_type for ct in card.card_types],
        "card_supertypes": [st.card_supertype for st in card.supertypes],
        "card_subtypes": [st.card_subtype for st in card.subtypes],
        "text": card.oracle_text,
        "power": card.power,
        "toughness": card.toughness,
    }


_PROMPTS_DIR = Path(__file__).parent
SYSTEM_PROMPT = (_PROMPTS_DIR / "system_prompt.md").read_text().strip()
_USER_PROMPT_TEMPLATE = (_PROMPTS_DIR / "user_prompt.md").read_text()


def _build_user_message(tag_description: str, cards: list[dict[str, object]]) -> str:
    cards_json = json.dumps(cards, indent=2)
    return _USER_PROMPT_TEMPLATE.format(tag_description=tag_description, cards_json=cards_json)


def _call_claude(
    client: anthropic.Anthropic,
    model: str,
    max_tokens: int,
    tag_description: str,
    cards: list[dict[str, object]],
    claude_log_path: Path,
) -> tuple[list[str], list[str]]:
    """Call Claude and return (tag_ids, unsure_ids)."""
    user_message = _build_user_message(tag_description, cards)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    text_blocks = [b for b in response.content if b.type == "text"]
    raw = text_blocks[0].text.strip() if text_blocks else ""

    with claude_log_path.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "user_message": user_message,
                    "raw_response": raw,
                    "stop_reason": response.stop_reason,
                    "model": response.model,
                }
            )
            + "\n"
        )

    if not text_blocks:
        logger.warning(
            "Claude returned no text blocks (stop_reason={}); skipping page.",
            response.stop_reason,
        )
        return [], []
    if not raw:
        logger.warning(
            "Claude returned empty text (stop_reason={}); skipping page.",
            response.stop_reason,
        )
        return [], []
    # Strip markdown code fences if the model ignored the formatting instruction.
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        raw = raw.rsplit("```", 1)[0].strip()
    parsed = json.loads(raw)
    input_ids = {str(c["oracle_id"]) for c in cards}
    returned_ids = set(parsed.get("tag", [])) | set(parsed.get("unsure", []))
    hallucinated = returned_ids - input_ids
    if hallucinated:
        raise ValueError(
            f"Claude returned {len(hallucinated)} oracle ID(s) not in the input: {hallucinated}"
        )
    return list(parsed.get("tag", [])), list(parsed.get("unsure", []))


async def _run(
    tag_name: str,
    client: anthropic.Anthropic,
    include_unsure: bool,
    include_excluded: bool,
) -> None:
    session_factory = get_async_session_factory()
    settings = get_settings()

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

    debug_dir = Path(settings.debug_output_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)
    claude_log_path = debug_dir / "claude.jsonl"
    page_num = 0
    total_tagged = 0
    total_unsure = 0
    total_excluded = 0

    # First page.
    async with session_factory() as session:
        page: SweepPage = await _sweep_service.resume_sweep(
            session, tag_name, settings.tag_sweep_limit
        )
        await session.commit()

    processed = page.already_processed

    while not page.is_complete:
        page_num += 1
        current_cards = page.cards
        total_pending = page.total_pending
        card_dicts = [_card_to_dict(c) for c in current_cards]

        tag_ids, unsure_ids = _call_claude(
            client, settings.tag_sweep_model, settings.tag_sweep_max_tokens,
            tag.description, card_dicts, claude_log_path,
        )

        classified = set(tag_ids) | set(unsure_ids)
        excluded_ids = [c.oracle_id for c in current_cards if c.oracle_id not in classified]

        # Apply tags and advance cursor in one session so they commit atomically.
        async with session_factory() as session:
            if tag_ids:
                await _tag_service.add_card_tags(session, tag_name, tag_ids)
            if include_unsure and unsure_ids:
                await _tag_service.add_card_tags(session, unsure_tag_name, unsure_ids)
            if include_excluded and excluded_ids:
                await _tag_service.add_card_tags(session, excluded_tag_name, excluded_ids)
            page = await _sweep_service.advance_and_fetch(
                session, tag_name, page.next_cursor, settings.tag_sweep_limit
            )
            await session.commit()

        total_tagged += len(tag_ids)
        total_unsure += len(unsure_ids)
        total_excluded += len(excluded_ids)
        processed += len(current_cards)

        pct = round(processed / total_pending * 100) if total_pending else 0
        logger.info(
            "Page {page} | tagged: {tagged} | unsure: {unsure} | excluded: {excluded}"
            " | processed: {processed} / {total} ({pct}%)",
            page=page_num,
            tagged=len(tag_ids),
            unsure=len(unsure_ids),
            excluded=len(excluded_ids),
            processed=processed,
            total=total_pending,
            pct=pct,
        )

    logger.info(
        "Done. Total tagged: {} | Total unsure: {} | Total excluded: {}",
        total_tagged, total_unsure, total_excluded,
    )


def main() -> None:
    _configure_logging()
    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY is not set — required for the tag sweep task.")
        sys.exit(1)
    args = _parse_args()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    asyncio.run(_run(args.tag, client, args.include_unsure, args.include_excluded))


if __name__ == "__main__":
    main()
