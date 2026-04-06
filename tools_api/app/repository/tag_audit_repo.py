"""Repository for ``magic_boto.tag_audit`` records."""

from __future__ import annotations

import uuid
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TagAuditModel


class TagAuditRepo:
    """Pure ORM access for ``tag_audit`` rows."""

    async def create_audit(self, session: AsyncSession, tag_id: uuid.UUID) -> TagAuditModel:
        """Insert a new audit row. Caller must flush/commit."""
        audit = TagAuditModel(tag_id=tag_id)
        session.add(audit)
        await session.flush()
        return audit

    async def get_audit(self, session: AsyncSession, audit_id: uuid.UUID) -> TagAuditModel | None:
        """Return an audit by ID, or None."""
        return await session.get(TagAuditModel, audit_id)

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
        """Delete all audit rows for a tag. Returns the number of rows deleted."""
        result = cast(
            CursorResult[tuple[()]],
            await session.execute(delete(TagAuditModel).where(TagAuditModel.tag_id == tag_id)),
        )
        return result.rowcount or 0
