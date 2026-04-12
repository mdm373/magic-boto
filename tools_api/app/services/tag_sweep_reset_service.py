"""Service for deleting an open sweep run for a tag."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.repository import TagRepo, TagSweepRepo


@dataclass(frozen=True, slots=True)
class SweepDeleteResult:
    deleted_sweep_id: str | None


class TagSweepResetService:
    def __init__(self, sweep_repo: TagSweepRepo, tag_repo: TagRepo) -> None:
        self._sweep_repo = sweep_repo
        self._tag_repo = tag_repo

    async def delete_open_sweep(self, session: AsyncSession, tag_name: str) -> SweepDeleteResult:
        tag = await self._tag_repo.get_tag_model(session, tag_name)
        if tag is None:
            raise NotFoundError(f"Tag '{tag_name}' not found.")
        deleted_id = await self._sweep_repo.delete_open_sweep(session, tag.id)
        return SweepDeleteResult(deleted_sweep_id=str(deleted_id) if deleted_id else None)


def create_tag_sweep_reset_service() -> TagSweepResetService:
    return TagSweepResetService(TagSweepRepo(), TagRepo())
