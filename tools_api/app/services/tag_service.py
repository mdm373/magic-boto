"""Tag CRUD: create/read/delete user-defined tags."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MagicBotoTagModel
from app.schema.tag_schema import Tag


def _canonical_tag_name(name: str) -> str:
    return name.strip().lower()


class TagService:
    """Create, read, and delete tags."""

    async def list_tags(self, session: AsyncSession) -> list[Tag]:
        """Return all tags sorted by name."""
        stmt = select(MagicBotoTagModel).order_by(MagicBotoTagModel.name.asc())
        result = await session.execute(stmt)
        return [Tag(name=row.name, description=row.description) for row in result.scalars().all()]

    async def get_tag(self, session: AsyncSession, name: str) -> Tag | None:
        """Return a tag by canonical name, or None if not found."""
        canonical = _canonical_tag_name(name)
        stmt = select(MagicBotoTagModel).where(MagicBotoTagModel.name == canonical)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        return Tag(name=row.name, description=row.description) if row else None

    async def create_tag(self, session: AsyncSession, name: str, description: str) -> Tag:
        """Insert a new tag; does not commit (caller owns the transaction)."""
        canonical = _canonical_tag_name(name)
        tag = MagicBotoTagModel(name=canonical, description=description.strip())
        session.add(tag)
        await session.flush()
        await session.refresh(tag)
        return Tag(name=tag.name, description=tag.description)

    async def delete_tag(self, session: AsyncSession, name: str) -> bool:
        """Delete a tag by canonical name. Returns True if deleted, False if not found."""
        canonical = _canonical_tag_name(name)
        stmt = delete(MagicBotoTagModel).where(MagicBotoTagModel.name == canonical)
        result: CursorResult[Any] = await session.execute(stmt)  # type: ignore[assignment]
        return (result.rowcount or 0) > 0
