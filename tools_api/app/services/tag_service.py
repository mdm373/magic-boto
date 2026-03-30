"""Tag CRUD: create/read/delete user-defined tags; apply/remove tags from cards."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult  # used by delete_tag
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import InvalidRequestError
from app.models import MagicBotoCardTagModel, MagicBotoTagModel
from app.models.magic_boto_card import MagicBotoCardModel
from app.schema.tag_schema import Tag


def _canonical_tag_name(name: str) -> str:
    return name.strip().lower()


class TagService:
    """Create, read, and delete tags; apply and remove tags from cards."""

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

    async def add_card_tags(
        self,
        session: AsyncSession,
        tag_name: str,
        oracle_ids: Sequence[str],
    ) -> bool:
        """Apply a tag to the given oracle IDs.

        Tagging is oracle-scoped: all printings of the same card share the tag.
        Returns False if the tag does not exist.
        Raises InvalidRequestError for unknown oracle_ids.
        Does not commit; caller owns the transaction.
        """
        canonical = _canonical_tag_name(tag_name)
        tag_row = await session.scalar(
            select(MagicBotoTagModel).where(MagicBotoTagModel.name == canonical)
        )
        if tag_row is None:
            return False

        found_ids = set(
            (
                await session.execute(
                    select(MagicBotoCardModel.oracle_id).where(
                        MagicBotoCardModel.oracle_id.in_(list(oracle_ids))
                    )
                )
            ).scalars().all()
        )
        not_found = [oid for oid in oracle_ids if oid not in found_ids]
        if not_found:
            raise InvalidRequestError(f"Oracle IDs not found: {', '.join(not_found)}")

        stmt = (
            pg_insert(MagicBotoCardTagModel)
            .values([{"tag_id": tag_row.id, "oracle_id": oid} for oid in found_ids])
            .on_conflict_do_nothing(index_elements=["tag_id", "oracle_id"])
        )
        await session.execute(stmt)
        return True

    async def remove_card_tags(
        self,
        session: AsyncSession,
        tag_name: str,
        oracle_ids: Sequence[str],
    ) -> bool:
        """Remove a tag from the given oracle IDs.

        Returns False if the tag does not exist.
        Raises InvalidRequestError for unknown oracle_ids.
        Does not commit; caller owns the transaction.
        """
        canonical = _canonical_tag_name(tag_name)
        tag_row = await session.scalar(
            select(MagicBotoTagModel).where(MagicBotoTagModel.name == canonical)
        )
        if tag_row is None:
            return False

        found_ids = set(
            (
                await session.execute(
                    select(MagicBotoCardModel.oracle_id).where(
                        MagicBotoCardModel.oracle_id.in_(list(oracle_ids))
                    )
                )
            ).scalars().all()
        )
        not_found = [oid for oid in oracle_ids if oid not in found_ids]
        if not_found:
            raise InvalidRequestError(f"Oracle IDs not found: {', '.join(not_found)}")

        await session.execute(
            delete(MagicBotoCardTagModel).where(
                MagicBotoCardTagModel.tag_id == tag_row.id,
                MagicBotoCardTagModel.oracle_id.in_(list(found_ids)),
            )
        )
        return True
