"""Unattended Claude-driven tag audit — samples tagged/excluded/unsure cards for quality review."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import anthropic
from loguru import logger

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.services import create_tag_service
from app.tag.card_payload import card_to_dict
from settings import get_settings

_tag_service = create_tag_service()

_PROMPTS_DIR = Path(__file__).parent
_SYSTEM_PROMPT = (_PROMPTS_DIR / "system_prompt.md").read_text().strip()
_USER_PROMPT_TEMPLATE = (_PROMPTS_DIR / "user_prompt.md").read_text()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Claude-driven tag audit.")
    parser.add_argument("tag", help="Tag name to audit (sweep results must already exist).")
    parser.add_argument(
        "--tagged-sample",
        type=int,
        default=20,
        metavar="N",
        help="Random tagged cards to sample (default: 20).",
    )
    parser.add_argument(
        "--excluded-sample",
        type=int,
        default=20,
        metavar="N",
        help="Random excluded cards to sample (default: 20).",
    )
    parser.add_argument(
        "--unsure-sample",
        type=int,
        default=10,
        metavar="N",
        help="Random unsure cards to sample (default: 10).",
    )
    return parser.parse_args()


async def _run(
    tag_name: str,
    tagged_sample: int,
    excluded_sample: int,
    unsure_sample: int,
) -> None:
    session_factory = get_async_session_factory()
    settings = get_settings()

    unsure_tag_name = f"{tag_name}_unsure"
    excluded_tag_name = f"{tag_name}_excluded"

    async with session_factory() as session:
        tag = await _tag_service.get_tag(session, tag_name)
        if tag is None:
            logger.error("Tag '{}' not found.", tag_name)
            sys.exit(1)

        tagged_cards = await _tag_service.sample_cards_for_tag(session, tag_name, tagged_sample)
        excluded_cards = await _tag_service.sample_cards_for_tag(
            session, excluded_tag_name, excluded_sample
        )
        unsure_cards = await _tag_service.sample_cards_for_tag(
            session, unsure_tag_name, unsure_sample
        )

    logger.info(
        "Sampled {} tagged / {} excluded / {} unsure cards for tag '{}'.",
        len(tagged_cards),
        len(excluded_cards),
        len(unsure_cards),
        tag_name,
    )

    tagged_dicts = [card_to_dict(card) for card in tagged_cards]
    excluded_dicts = [card_to_dict(card) for card in excluded_cards]
    unsure_dicts = [card_to_dict(card) for card in unsure_cards]

    user_message = _USER_PROMPT_TEMPLATE.format(
        tag_name=tag_name,
        tag_description=tag.description,
        tagged_count=len(tagged_dicts),
        excluded_count=len(excluded_dicts),
        unsure_count=len(unsure_dicts),
        tagged_json=json.dumps(tagged_dicts, indent=2),
        excluded_json=json.dumps(excluded_dicts, indent=2),
        unsure_json=json.dumps(unsure_dicts, indent=2),
    )

    logger.info("Calling {} for audit...", settings.tag_audit_model)
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.tag_audit_model,
        max_tokens=settings.tag_audit_max_tokens,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    if response.stop_reason == "max_tokens":
        logger.warning(
            "Audit response was truncated at {} tokens — consider raising tag_audit_max_tokens.",
            settings.tag_audit_max_tokens,
        )
    text_blocks = [b for b in response.content if b.type == "text"]
    audit_text = text_blocks[0].text.strip() if text_blocks else "(No response from model)"

    debug_dir = Path(settings.debug_output_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    output_path = debug_dir / f"{timestamp}_{tag_name}_audit.md"
    output_path.write_text(audit_text, encoding="utf-8")
    logger.info("Audit saved to {}.", output_path)
    os.startfile(str(output_path))


def main() -> None:
    configure_cli_logging()
    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY is not set — required for the tag audit task.")
        sys.exit(1)
    args = _parse_args()
    asyncio.run(_run(args.tag, args.tagged_sample, args.excluded_sample, args.unsure_sample))


if __name__ == "__main__":
    main()
