"""Sample cards and enqueue an Anthropic batch for tag quality audit (outbox on ``batches``).

Used by ``app.cmd.tag.audit.enqueue`` and the Celery sweep pipeline (audit-after).
Submit runs in Celery ``submit_batch``; ``payload`` is JSON (same envelope as sweeps)
with one Anthropic batch item until then.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TagAuditModel, TagModel
from app.prompts import AUDIT_PROMPTS_DIR
from app.repository import BatchRepo, TagAuditRepo, TagRepo
from settings import get_settings

from .batch_client import Request
from .batch_serialization_service import (
    BatchSerializationService,
    create_batch_serialization_service,
)
from .card_payload import cards_to_csv_with_names
from .tag_service import TagService

AUDIT_SYSTEM_PROMPT = (AUDIT_PROMPTS_DIR / "system_prompt.md").read_text(encoding="utf-8").strip()
_USER_PROMPT_TEMPLATE = (AUDIT_PROMPTS_DIR / "user_prompt.md").read_text(encoding="utf-8")


@dataclass(frozen=True, slots=True)
class AuditKickoffResult:
    """Return from audit kickoff methods for enqueue wiring."""

    audit_id: uuid.UUID
    batch_id: uuid.UUID


class TagAuditInitService:
    """Create an audit row and submit a batch using injected repos, tag service, and API client."""

    def __init__(
        self,
        *,
        tag_service: TagService,
        audit_repo: TagAuditRepo,
        batch_repo: BatchRepo,
        tag_repo: TagRepo,
        batch_serialization: BatchSerializationService,
    ) -> None:
        self._tag_service = tag_service
        self._audit_repo = audit_repo
        self._batch_repo = batch_repo
        self._tag_repo = tag_repo
        self._batch_serialization = batch_serialization

    async def init_audit(
        self,
        session: AsyncSession,
        tag_name: str,
        tagged_count: int,
        excluded_count: int,
        unsure_count: int,
    ) -> AuditKickoffResult:
        """Create audit row and pending outbox batch"""
        tag = await self._tag_repo.require_tag_model(session, tag_name, load_relationships=True)
        audit = await self._audit_repo.create_audit(
            session,
            tag.id,
            audit_tagged_sample=tagged_count,
            audit_excluded_sample=excluded_count,
            audit_unsure_sample=unsure_count,
        )
        return await self._kickoff_audit_batch(session, audit, tag, tag_name)

    async def create_audit_batches(
        self,
        session: AsyncSession,
        audit_id: uuid.UUID,
    ) -> AuditKickoffResult:
        """For existing audit row, create pending outbox batch"""
        audit = await self._audit_repo.get_audit(session, audit_id)
        if audit is None:
            raise ValueError(f"Audit {audit_id} not found.")
        if audit.batch_id is not None:
            raise ValueError(f"Audit {audit_id} already has a batch assigned.")
        tag_id = audit.tag_id
        tag = await self._tag_repo.require_tag_model_by_id(session, tag_id, load_relationships=True)
        return await self._kickoff_audit_batch(session, audit, tag, tag.name)

    async def _kickoff_audit_batch(
        self,
        session: AsyncSession,
        audit: TagAuditModel,
        tag: TagModel,
        tag_name: str,
    ) -> AuditKickoffResult:
        settings = get_settings()
        tag_service = self._tag_service
        unsure = f"{tag_name}_unsure"
        exclude = f"{tag_name}_excluded"
        tagged_sample = audit.audit_tagged_sample
        excluded_sample = audit.audit_excluded_sample
        unsure_sample = audit.audit_unsure_sample
        tagged_cards = await tag_service.sample_cards_for_tag(session, tag_name, tagged_sample)
        excluded_cards = await tag_service.sample_cards_for_tag(session, exclude, excluded_sample)
        unsure_cards = await tag_service.sample_cards_for_tag(session, unsure, unsure_sample)
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

        logger.info("Using model: {} (batch submit via Celery)", settings.tag_audit_model)
        batch = await self._batch_repo.create_pending_batch(session)
        await self._audit_repo.attach_batch(session, audit, batch.id)
        await self._batch_repo.set_batch_payload(
            session,
            batch,
            self._batch_serialization.serialize_requests(
                [
                    Request(
                        custom_id="audit",
                        messages=[user_message],
                        model=settings.tag_audit_model,
                        max_tokens=settings.tag_audit_max_tokens,
                        system_prompt=AUDIT_SYSTEM_PROMPT,
                    )
                ]
            ),
        )
        logger.info("Audit ID: {} | pending batch: {}", audit.id, batch.id)
        return AuditKickoffResult(audit_id=audit.id, batch_id=batch.id)


def create_tag_audit_init_service() -> TagAuditInitService:
    """Wiring for CLI, Celery, and tests."""
    return TagAuditInitService(
        tag_service=TagService(),
        audit_repo=TagAuditRepo(),
        batch_repo=BatchRepo(),
        tag_repo=TagRepo(),
        batch_serialization=create_batch_serialization_service(),
    )
