"""Batch poll providers for tag sweep and tag audit pipelines (Celery worker)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.repository import TagAuditRepo
from app.repository.tag_repo import TagRepo
from app.repository.tag_sweep_repo import TagSweepRepo


class SweepPollProvider:
    """Resolve batch IDs for the open sweep for a tag."""

    def __init__(
        self,
        tag_name: str,
        *,
        sweep_repo: TagSweepRepo,
        tag_repo: TagRepo,
    ) -> None:
        self._tag_name = tag_name
        self._sweep_repo = sweep_repo
        self._tag_repo = tag_repo

    async def fetch_batch_ids(self, session: AsyncSession) -> Sequence[uuid.UUID]:
        tag = await self._tag_repo.require_tag_model(session, self._tag_name)
        sweep = await self._sweep_repo.get_open_sweep(session, tag.id)
        if sweep is None:
            raise ValueError(f"No open sweep found for tag '{self._tag_name}'.")
        sweep_batches = await self._sweep_repo.get_batches(session, sweep.id)
        return [sb.batch_id for sb in sweep_batches]


class AuditPollProvider:
    """Resolve batch ID for a tag audit."""

    def __init__(
        self,
        audit_id: uuid.UUID,
        *,
        audit_repo: TagAuditRepo,
    ) -> None:
        self._audit_id = audit_id
        self._audit_repo = audit_repo

    async def fetch_batch_ids(self, session: AsyncSession) -> Sequence[uuid.UUID]:
        audit = await self._audit_repo.get_audit(session, self._audit_id)
        if audit is None:
            raise ValueError(f"Audit {self._audit_id} not found.")
        if audit.batch is None:
            raise ValueError(f"Audit {self._audit_id} has no batch — run kickoff first.")
        return [audit.batch.id]


def create_sweep_poll_provider(tag_name: str) -> SweepPollProvider:
    """Build a sweep poll provider with default repos."""
    return SweepPollProvider(tag_name, sweep_repo=TagSweepRepo(), tag_repo=TagRepo())


def create_audit_poll_provider(audit_id: uuid.UUID) -> AuditPollProvider:
    """Build an audit poll provider with the default repo."""
    return AuditPollProvider(audit_id, audit_repo=TagAuditRepo())
