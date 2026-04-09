"""Sample cards and submit an Anthropic batch for tag quality audit.

Used by ``app.cmd.tag.audit.enqueue`` (tag argument) and the Celery sweep pipeline (audit-after).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository import BatchRepo, TagAuditRepo, TagRepo
from settings import get_settings

from .batch_client import BatchApiClient, Request, create_batch_client
from .card_payload import cards_to_csv_with_names
from .tag_service import TagService

_PROMPTS_DIR = Path("app/prompts/audit")
_SYSTEM_PROMPT = (_PROMPTS_DIR / "system_prompt.md").read_text().strip()
_USER_PROMPT_TEMPLATE = (_PROMPTS_DIR / "user_prompt.md").read_text()


class TagAuditInitializer:
    """Create an audit row and submit a batch using injected repos, tag service, and API client."""

    def __init__(
        self,
        *,
        tag_service: TagService,
        audit_repo: TagAuditRepo,
        batch_repo: BatchRepo,
        tag_repo: TagRepo,
        batch_api_client: BatchApiClient,
    ) -> None:
        self._tag_service = tag_service
        self._audit_repo = audit_repo
        self._batch_repo = batch_repo
        self._tag_repo = tag_repo
        self._batch_api_client = batch_api_client

    async def init_audit(
        self,
        session: AsyncSession,
        tag_name: str,
        tagged_count: int,
        excluded_count: int,
        unsure_count: int,
    ) -> uuid.UUID:
        """Create audit row and submit batch"""
        settings = get_settings()
        tag_service = self._tag_service
        unsure = f"{tag_name}_unsure"
        exclude = f"{tag_name}_excluded"
        tag = await self._tag_repo.require_tag_model(session, tag_name)
        tagged_cards = await tag_service.sample_cards_for_tag(session, tag_name, tagged_count)
        excluded_cards = await tag_service.sample_cards_for_tag(session, exclude, excluded_count)
        unsure_cards = await tag_service.sample_cards_for_tag(session, unsure, unsure_count)
        logger.info(
            "Sampled {} tagged / {} excluded / {} unsure cards for tag '{}'.",
            len(tagged_cards),
            len(excluded_cards),
            len(unsure_cards),
            tag_name,
        )
        tagged_csv = cards_to_csv_with_names(tagged_cards)
        excluded_csv = cards_to_csv_with_names(excluded_cards)
        unsure_csv = cards_to_csv_with_names(unsure_cards)
        user_message = _USER_PROMPT_TEMPLATE.format(
            tag_name=tag_name,
            tag_description=tag.description,
            tagged_count=len(tagged_cards),
            excluded_count=len(excluded_cards),
            unsure_count=len(unsure_cards),
            tagged_csv=tagged_csv,
            excluded_csv=excluded_csv,
            unsure_csv=unsure_csv,
        )

        logger.info("Using model: {}", settings.tag_audit_model)
        anthropic_batch_id = self._batch_api_client.submit_requests(
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
        audit = await self._audit_repo.create_audit(session, tag.id)
        batch = await self._batch_repo.create_batch(session, anthropic_batch_id)
        audit.batch_id = batch.id
        audit_id: uuid.UUID = audit.id
        logger.info("Audit ID: {} | Batch: {}", audit_id, anthropic_batch_id)
        return audit_id


def create_tag_audit_initializer() -> TagAuditInitializer:
    """Wiring for CLI, Celery, and tests."""
    return TagAuditInitializer(
        tag_service=TagService(),
        audit_repo=TagAuditRepo(),
        batch_repo=BatchRepo(),
        tag_repo=TagRepo(),
        batch_api_client=create_batch_client(),
    )
