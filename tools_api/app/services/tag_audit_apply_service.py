"""Service for applying an audit suggestion to a tag."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import InvalidRequestError, NotFoundError
from app.repository import CardTagRepo, TagAuditRepo, TagRepo, TagSweepRepo


@dataclass(frozen=True, slots=True)
class AuditApplyResult:
    new_description: str
    cards_cleared: int


class TagAuditApplyService:
    def __init__(
        self,
        audit_repo: TagAuditRepo,
        tag_repo: TagRepo,
        card_tag_repo: CardTagRepo,
        sweep_repo: TagSweepRepo,
    ) -> None:
        self._audit_repo = audit_repo
        self._tag_repo = tag_repo
        self._card_tag_repo = card_tag_repo
        self._sweep_repo = sweep_repo

    async def apply(
        self,
        session: AsyncSession,
        tag_name: str,
        *,
        delete_tagged: bool,
        delete_side_tags: bool,
    ) -> AuditApplyResult:
        tag = await self._tag_repo.get_tag_model(session, tag_name)
        if tag is None:
            raise NotFoundError(f"Tag '{tag_name}' not found.")
        audit = await self._audit_repo.get_latest_for_tag(session, tag.id)
        if audit is None:
            raise NotFoundError(f"No audit found for tag '{tag_name}'.")
        if audit.suggestion is None:
            raise InvalidRequestError(
                f"Latest audit for '{tag_name}' has no suggestion — run audit.process first."
            )

        updated = await self._tag_repo.update_description(session, tag_name, audit.suggestion)
        if not updated:
            raise NotFoundError(f"Tag '{tag_name}' not found when updating description.")

        cards_cleared = 0

        if delete_tagged or delete_side_tags:
            main_tag = await self._tag_repo.get_tag_model(session, tag_name)
            if main_tag is not None and delete_tagged:
                cards_cleared += await self._card_tag_repo.delete_all_for_tag(session, main_tag.id)

            if delete_side_tags:
                for suffix in ("_unsure", "_excluded"):
                    side = await self._tag_repo.get_tag_model(session, f"{tag_name}{suffix}")
                    if side is not None:
                        cards_cleared += await self._card_tag_repo.delete_all_for_tag(
                            session, side.id
                        )

            if delete_side_tags:
                for suffix in ("_unsure", "_excluded"):
                    await self._tag_repo.delete_tag(session, f"{tag_name}{suffix}")

        if delete_tagged:
            await self._sweep_repo.delete_sweep_batch_history_for_tag(session, tag.id)
            await self._sweep_repo.reset_epoch_for_tag(session, tag.id)

        return AuditApplyResult(new_description=audit.suggestion, cards_cleared=cards_cleared)


def create_tag_audit_apply_service() -> TagAuditApplyService:
    return TagAuditApplyService(TagAuditRepo(), TagRepo(), CardTagRepo(), TagSweepRepo())
