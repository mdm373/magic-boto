"""Tag audit kickoff — sample cards and submit an Anthropic batch for review."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from loguru import logger

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.repository import BatchRepo, TagAuditRepo, TagRepo
from app.services import Request, card_to_dict, create_batch_client, create_tag_service
from settings import get_settings

_tag_service = create_tag_service()
_audit_repo = TagAuditRepo()
_batch_repo = BatchRepo()
_tag_repo = TagRepo()

_PROMPTS_DIR = Path("app/prompts/audit")
_SYSTEM_PROMPT = (_PROMPTS_DIR / "system_prompt.md").read_text().strip()
_USER_PROMPT_TEMPLATE = (_PROMPTS_DIR / "user_prompt.md").read_text()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit a tag audit batch to Anthropic.")
    parser.add_argument("tag", help="Tag name to audit (sweep results must already exist).")
    parser.add_argument("--tagged-sample", type=int, default=20, metavar="N")
    parser.add_argument("--excluded-sample", type=int, default=20, metavar="N")
    parser.add_argument("--unsure-sample", type=int, default=10, metavar="N")
    return parser.parse_args()


async def _run(
    tag_name: str,
    tagged_sample: int,
    excluded_sample: int,
    unsure_sample: int,
) -> uuid.UUID:
    settings = get_settings()
    session_factory = get_async_session_factory()

    unsure_tag_name = f"{tag_name}_unsure"
    excluded_tag_name = f"{tag_name}_excluded"

    async with session_factory() as session:
        tag = await _tag_repo.require_tag_model(session, tag_name)

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

    batch_client = create_batch_client()
    logger.info("Using model: {}", settings.tag_audit_model)
    anthropic_batch_id = batch_client.submit_requests(
        [
            Request(
                custom_id="audit",
                messages=[user_message],
                model=settings.tag_audit_model,
                max_tokens=settings.tag_audit_max_tokens,
                system_prompt=_SYSTEM_PROMPT,
            )
        ]
    )

    async with session_factory() as session:
        audit = await _audit_repo.create_audit(session, tag.id)
        batch = await _batch_repo.create_batch(session, anthropic_batch_id)
        audit.batch_id = batch.id
        audit_id: uuid.UUID = audit.id
        await session.commit()

    logger.info("Audit ID: {} | Batch: {}", audit_id, anthropic_batch_id)
    return audit_id


def main() -> None:
    configure_cli_logging()
    args = _parse_args()
    audit_id = asyncio.run(
        _run(args.tag, args.tagged_sample, args.excluded_sample, args.unsure_sample)
    )
    print(audit_id, flush=True)


if __name__ == "__main__":
    main()
