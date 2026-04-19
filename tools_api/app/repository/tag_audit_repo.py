"""Repository for ``magic_boto.tag_audit`` records."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BatchModel, TagAuditModel


class TagAuditRepo:
    """Pure ORM access for ``tag_audit`` rows."""

    async def attach_batch(
        self,
        session: AsyncSession,
        audit: TagAuditModel,
        batch_id: uuid.UUID,
    ) -> None:
        """Set audit.batch_id. Caller commits."""
        audit.batch_id = batch_id
        await session.flush()

    async def set_report_and_suggestion(
        self,
        session: AsyncSession,
        audit: TagAuditModel,
        *,
        report: str,
        suggestion: str | None,
    ) -> None:
        """Set audit report fields. Caller commits."""
        audit.report = report
        audit.suggestion = suggestion
        await session.flush()

    async def create_audit(
        self,
        session: AsyncSession,
        tag_id: uuid.UUID,
        *,
        audit_tagged_sample: int = 20,
        audit_excluded_sample: int = 70,
        audit_unsure_sample: int = 10,
    ) -> TagAuditModel:
        """Insert a new audit row. Caller must flush/commit."""
        audit = TagAuditModel(
            tag_id=tag_id,
            audit_tagged_sample=audit_tagged_sample,
            audit_excluded_sample=audit_excluded_sample,
            audit_unsure_sample=audit_unsure_sample,
        )
        session.add(audit)
        await session.flush()
        return audit

    async def get_audit(self, session: AsyncSession, audit_id: uuid.UUID) -> TagAuditModel | None:
        """Return an audit by ID, or None."""
        return await session.get(TagAuditModel, audit_id)

    async def get_audit_by_batch_id(
        self, session: AsyncSession, batch_id: uuid.UUID
    ) -> TagAuditModel | None:
        """Return the audit row linked to this batch id, or None."""
        return cast(
            TagAuditModel | None,
            await session.scalar(
                select(TagAuditModel).where(TagAuditModel.batch_id == batch_id).limit(1)
            ),
        )

    async def get_audits_by_batch_ids(
        self, session: AsyncSession, batch_ids: Sequence[uuid.UUID]
    ) -> list[TagAuditModel]:
        """Return audits with ``batch_id`` in ``batch_ids`` (order not preserved)."""
        if not batch_ids:
            return []
        result = await session.execute(
            select(TagAuditModel).where(TagAuditModel.batch_id.in_(batch_ids))
        )
        return list(result.scalars().all())

    async def get_latest_for_tag(
        self, session: AsyncSession, tag_id: uuid.UUID
    ) -> TagAuditModel | None:
        """Return the most recent audit for a tag, or None."""
        return cast(
            TagAuditModel | None,
            await session.scalar(
                select(TagAuditModel)
                .where(TagAuditModel.tag_id == tag_id)
                .order_by(TagAuditModel.triggered_at.desc())
                .limit(1)
            ),
        )

    async def delete_audits_for_tag(self, session: AsyncSession, tag_id: uuid.UUID) -> int:
        """Delete all audit rows for a tag. Returns the number of rows deleted.

        Deletes linked ``batches`` rows first (same session) so outbox payloads are
        removed; ``tag_audit.batch_id`` FK uses ON DELETE SET NULL so rows stay
        consistent until the audit delete runs.
        """
        audit_batch_ids = select(TagAuditModel.batch_id).where(
            TagAuditModel.tag_id == tag_id,
            TagAuditModel.batch_id.is_not(None),
        )
        await session.execute(delete(BatchModel).where(BatchModel.id.in_(audit_batch_ids)))
        result = cast(
            CursorResult[tuple[()]],
            await session.execute(delete(TagAuditModel).where(TagAuditModel.tag_id == tag_id)),
        )
        return result.rowcount or 0
