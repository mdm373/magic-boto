"""Tag audit invariants and lookups for workers and pipelines."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.repository import TagAuditRepo


class TagAuditService:
    """Tag audit queries and pipeline invariants."""

    def __init__(self, *, audit_repo: TagAuditRepo) -> None:
        self._audit_repo = audit_repo

    async def require_single_audit_id_for_batch_ids(
        self,
        session: AsyncSession,
        batch_ids: Sequence[uuid.UUID],
    ) -> uuid.UUID:
        """Return the audit id when every batch id maps to the same ``tag_audit`` row."""
        if not batch_ids:
            raise ValueError("batch_ids must be non-empty.")
        rows = await self._audit_repo.get_audits_by_batch_ids(session, batch_ids)
        by_batch_id: dict[uuid.UUID, uuid.UUID] = {}
        for row in rows:
            if row.batch_id is not None:
                by_batch_id[row.batch_id] = row.id
        audit_ids: set[uuid.UUID] = set()
        for bid in batch_ids:
            audit_id = by_batch_id.get(bid)
            if audit_id is None:
                raise ValueError(f"No tag audit row linked to batch {bid}.")
            audit_ids.add(audit_id)
        if len(audit_ids) != 1:
            raise ValueError("batch_ids must belong to exactly one tag audit.")
        return next(iter(audit_ids))


def create_tag_audit_service() -> TagAuditService:
    """Default wiring for workers and tests."""
    return TagAuditService(audit_repo=TagAuditRepo())


__all__ = ["TagAuditService", "create_tag_audit_service"]
