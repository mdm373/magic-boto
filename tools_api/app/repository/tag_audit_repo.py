"""Repository for ``magic_boto.tag_audit`` records."""

from __future__ import annotations

import uuid

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
