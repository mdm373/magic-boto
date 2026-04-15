"""Service for sweep run deletion and full clean reset before a new sweep."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.repository import CardTagRepo, TagAuditRepo, TagRepo, TagSweepRepo


@dataclass(frozen=True, slots=True)
class SweepDeleteResult:
    deleted_sweep_id: str | None


@dataclass(frozen=True, slots=True)
class CleanSweepResetResult:
    """Outcome of ``clean_reset_for_new_sweep`` (tag assignments + sweep artifacts)."""

    deleted_sweep_id: str | None
    cards_cleared: int
    batches_deleted: int


class TagSweepResetService:
    def __init__(
        self,
        sweep_repo: TagSweepRepo,
        tag_repo: TagRepo,
        card_tag_repo: CardTagRepo,
        audit_repo: TagAuditRepo,
    ) -> None:
        self._sweep_repo = sweep_repo
        self._tag_repo = tag_repo
        self._card_tag_repo = card_tag_repo
        self._audit_repo = audit_repo

    async def prune_side_tags_audits_and_sweep_batches(
        self,
        session: AsyncSession,
        tag_name: str,
    ) -> None:
        """Remove ``_unsure`` / ``_excluded`` side tags, all audits, and sweep batch history.

        Does not clear main-tag ``card_tags`` or the sweep epoch (for incremental catch-up).
        Caller must commit.
        """
        tag = await self._tag_repo.require_tag_model(session, tag_name)
        for suffix in ("_unsure", "_excluded"):
            await self._tag_repo.delete_tag(session, f"{tag_name}{suffix}")
        await self._audit_repo.delete_audits_for_tag(session, tag.id)
        await self._sweep_repo.delete_sweep_batch_history_for_tag(session, tag.id)

    async def delete_open_sweep(self, session: AsyncSession, tag_name: str) -> SweepDeleteResult:
        tag = await self._tag_repo.get_tag_model(session, tag_name)
        if tag is None:
            raise NotFoundError(f"Tag '{tag_name}' not found.")
        deleted_id = await self._sweep_repo.delete_open_sweep(session, tag.id)
        return SweepDeleteResult(deleted_sweep_id=str(deleted_id) if deleted_id else None)

    async def clean_reset_for_new_sweep(
        self,
        session: AsyncSession,
        tag_name: str,
    ) -> CleanSweepResetResult:
        """Clear tag assignments, side tags, audits, sweep batch history, epoch, open sweep.

        Matches the tag/sweep cleanup portion of ``TagAuditApplyService.apply`` with
        ``delete_tagged`` and ``delete_side_tags`` true, plus audit rows and ``delete_open_sweep``.
        """
        tag = await self._tag_repo.get_tag_model(session, tag_name)
        if tag is None:
            raise NotFoundError(f"Tag '{tag_name}' not found.")

        cards_cleared = 0
        cards_cleared += await self._card_tag_repo.delete_all_for_tag(session, tag.id)

        for suffix in ("_unsure", "_excluded"):
            side = await self._tag_repo.get_tag_model(session, f"{tag_name}{suffix}")
            if side is not None:
                cards_cleared += await self._card_tag_repo.delete_all_for_tag(session, side.id)

        for suffix in ("_unsure", "_excluded"):
            await self._tag_repo.delete_tag(session, f"{tag_name}{suffix}")

        await self._audit_repo.delete_audits_for_tag(session, tag.id)

        batches_deleted = await self._sweep_repo.delete_sweep_batch_history_for_tag(session, tag.id)
        await self._sweep_repo.reset_epoch_for_tag(session, tag.id)
        deleted_id = await self._sweep_repo.delete_open_sweep(session, tag.id)

        return CleanSweepResetResult(
            deleted_sweep_id=str(deleted_id) if deleted_id else None,
            cards_cleared=cards_cleared,
            batches_deleted=batches_deleted,
        )


def create_tag_sweep_reset_service() -> TagSweepResetService:
    return TagSweepResetService(TagSweepRepo(), TagRepo(), CardTagRepo(), TagAuditRepo())
