"""Repository for ``magic_boto.tags``."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_schema.tag_schema import Tag
from app.errors import InvalidRequestError
from app.models.tag_model import TagModel
from app.models.tag_supertype_model import TagSupertypeModel
from app.models.tag_type_model import TagTypeModel

from .canonical import canonical_name


def tag_from_model(row: TagModel) -> Tag:
    return Tag(
        name=row.name,
        description=row.description,
        sweep_include_types=[r.card_type for r in row.tag_types],
        sweep_include_supertypes=[r.card_supertype for r in row.supertypes],
    )


class TagRepo:
    """Pure ORM access for ``magic_boto.tags``."""

    async def list_tags(self, session: AsyncSession) -> Sequence[Tag]:
        """Return all tags sorted by name."""
        stmt = select(TagModel).order_by(TagModel.name.asc())
        result = await session.execute(stmt)
        return [tag_from_model(row) for row in result.scalars().all()]

    async def get_tag(self, session: AsyncSession, name: str) -> Tag | None:
        """Return a tag by canonical name, or None."""
        canonical = canonical_name(name)
        stmt = select(TagModel).where(TagModel.name == canonical)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        return tag_from_model(row) if row else None

    async def get_tag_model(
        self,
        session: AsyncSession,
        name: str,
        load_relationships: bool = False,
    ) -> TagModel | None:
        """Return the ORM tag model by canonical name, or None."""
        canonical = canonical_name(name)
        tag = await session.scalar(select(TagModel).where(TagModel.name == canonical))
        if tag is not None and load_relationships:
            _ = tag.tag_types
            _ = tag.supertypes
        return tag

    async def require_tag_model(
        self,
        session: AsyncSession,
        name: str,
        load_relationships: bool = False,
    ) -> TagModel:
        """Return the ORM tag model by canonical name. Raises ValueError if not found."""
        tag = await self.get_tag_model(session, name, load_relationships=load_relationships)
        if tag is None:
            raise ValueError(f"Tag '{name}' not found.")
        return tag

    async def get_tag_model_by_id(
        self,
        session: AsyncSession,
        tag_id: uuid.UUID,
        load_relationships: bool = False,
    ) -> TagModel | None:
        """Return the ORM tag model by ID, or None."""
        tag = await session.scalar(select(TagModel).where(TagModel.id == tag_id))
        if tag is not None and load_relationships:
            _ = tag.tag_types
            _ = tag.supertypes
        return tag

    async def require_tag_model_by_id(
        self,
        session: AsyncSession,
        tag_id: uuid.UUID,
        load_relationships: bool = False,
    ) -> TagModel:
        """Return the ORM tag model by ID. Raises ValueError if not found."""
        tag = await self.get_tag_model_by_id(session, tag_id, load_relationships=load_relationships)
        if tag is None:
            raise ValueError(f"Tag ID {tag_id} not found.")
        return tag

    async def create_tag(
        self,
        session: AsyncSession,
        name: str,
        description: str,
        sweep_include_types: Sequence[str] = (),
        sweep_include_supertypes: Sequence[str] = (),
    ) -> Tag:
        """Insert a new tag; does not commit (caller owns the transaction)."""
        canonical = canonical_name(name)
        tag = TagModel(
            name=canonical,
            description=description.strip(),
            tag_types=[
                TagTypeModel(card_type=t.strip().lower()) for t in sweep_include_types if t.strip()
            ],
            supertypes=[
                TagSupertypeModel(card_supertype=s.strip().lower())
                for s in sweep_include_supertypes
                if s.strip()
            ],
        )
        session.add(tag)
        await session.flush()
        await session.refresh(tag)
        return tag_from_model(tag)

    async def rename_tag(self, session: AsyncSession, old_name: str, new_name: str) -> bool:
        """Rename a tag. Returns False if not found; raises InvalidRequestError on name conflict."""
        old_canonical = canonical_name(old_name)
        new_canonical = canonical_name(new_name)
        row = await session.scalar(select(TagModel).where(TagModel.name == old_canonical))
        if row is None:
            return False
        existing = await session.scalar(select(TagModel).where(TagModel.name == new_canonical))
        if existing is not None:
            raise InvalidRequestError(f"Tag '{new_canonical}' already exists.")
        row.name = new_canonical
        await session.flush()
        return True

    async def delete_tag(self, session: AsyncSession, name: str) -> bool:
        """Delete a tag by canonical name. Returns True if deleted, False if not found."""
        canonical = canonical_name(name)
        result = cast(
            CursorResult[tuple[()]],
            await session.execute(delete(TagModel).where(TagModel.name == canonical)),
        )
        return (result.rowcount or 0) > 0

