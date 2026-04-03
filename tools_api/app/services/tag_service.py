"""Tag CRUD: create/read/delete user-defined tags; apply/remove tags from cards."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult  # used by delete_tag
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import InvalidRequestError
from app.models import MagicBotoCardTagModel, MagicBotoTagModel
from app.models.magic_boto_card import MagicBotoCardModel
from app.models.magic_boto_tag_supertype import MagicBotoTagSupertypeModel
from app.models.magic_boto_tag_type import MagicBotoTagTypeModel
from app.schema.tag_schema import Tag
from settings import get_settings


@dataclass(frozen=True, slots=True)
class CardTagEntry:
    """A single card-tagging request: the oracle_id to tag."""

    oracle_id: str


def _canonical_tag_name(name: str) -> str:
    return name.strip().lower()


def _tag_from_model(row: MagicBotoTagModel) -> Tag:
    return Tag(
        name=row.name,
        description=row.description,
        sweep_include_types=[r.card_type for r in row.tag_types],
        sweep_include_supertypes=[r.card_supertype for r in row.supertypes],
    )


class TagService:
    """Create, read, and delete tags; apply and remove tags from cards."""

    async def list_tags(self, session: AsyncSession) -> list[Tag]:
        """Return all tags sorted by name."""
        stmt = select(MagicBotoTagModel).order_by(MagicBotoTagModel.name.asc())
        result = await session.execute(stmt)
        return [_tag_from_model(row) for row in result.scalars().all()]

    async def get_tag(self, session: AsyncSession, name: str) -> Tag | None:
        """Return a tag by canonical name, or None if not found."""
        canonical = _canonical_tag_name(name)
        stmt = select(MagicBotoTagModel).where(MagicBotoTagModel.name == canonical)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        return _tag_from_model(row) if row else None

    async def get_tag_model(
        self,
        session: AsyncSession,
        name: str,
        load_relationships: bool = False,
    ) -> MagicBotoTagModel | None:
        """Return the ORM tag model by canonical name, or None if not found."""
        canonical = _canonical_tag_name(name)
        tag = await session.scalar(
            select(MagicBotoTagModel).where(MagicBotoTagModel.name == canonical)
        )
        if tag is not None and load_relationships:
            _ = tag.tag_types
            _ = tag.supertypes
        return tag

    async def require_tag_model(
        self,
        session: AsyncSession,
        name: str,
        load_relationships: bool = False,
    ) -> MagicBotoTagModel:
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
    ) -> MagicBotoTagModel | None:
        """Return the ORM tag model by ID, or None if not found."""
        tag = await session.scalar(
            select(MagicBotoTagModel).where(MagicBotoTagModel.id == tag_id)
        )
        if tag is not None and load_relationships:
            _ = tag.tag_types
            _ = tag.supertypes
        return tag

    async def require_tag_model_by_id(
        self,
        session: AsyncSession,
        tag_id: uuid.UUID,
        load_relationships: bool = False,
    ) -> MagicBotoTagModel:
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
        canonical = _canonical_tag_name(name)
        tag = MagicBotoTagModel(
            name=canonical,
            description=description.strip(),
            tag_types=[
                MagicBotoTagTypeModel(card_type=t.strip().lower())
                for t in sweep_include_types
                if t.strip()
            ],
            supertypes=[
                MagicBotoTagSupertypeModel(card_supertype=s.strip().lower())
                for s in sweep_include_supertypes
                if s.strip()
            ],
        )
        session.add(tag)
        await session.flush()
        await session.refresh(tag)
        return _tag_from_model(tag)

    async def rename_tag(self, session: AsyncSession, old_name: str, new_name: str) -> bool:
        """Rename a tag.

        Returns False if old_name not found; raises InvalidRequestError if new_name already exists.
        Does not commit; caller owns the transaction.
        """
        old_canonical = _canonical_tag_name(old_name)
        new_canonical = _canonical_tag_name(new_name)
        row = await session.scalar(
            select(MagicBotoTagModel).where(MagicBotoTagModel.name == old_canonical)
        )
        if row is None:
            return False
        existing = await session.scalar(
            select(MagicBotoTagModel).where(MagicBotoTagModel.name == new_canonical)
        )
        if existing is not None:
            raise InvalidRequestError(f"Tag '{new_canonical}' already exists.")
        row.name = new_canonical
        await session.flush()
        return True

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
        entries: Sequence[CardTagEntry],
    ) -> bool:
        """Apply a tag to the given card entries.

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

        entries_by_id = {e.oracle_id: e for e in entries}
        found_ids = set(
            (
                await session.execute(
                    select(MagicBotoCardModel.oracle_id).where(
                        MagicBotoCardModel.oracle_id.in_(list(entries_by_id))
                    )
                )
            )
            .scalars()
            .all()
        )
        not_found = [oid for oid in entries_by_id if oid not in found_ids]
        if not_found:
            raise InvalidRequestError(f"Oracle IDs not found: {', '.join(not_found)}")

        chunk_size = get_settings().db_insert_chunk_size
        found_list = list(found_ids)
        for i in range(0, len(found_list), chunk_size):
            chunk = found_list[i : i + chunk_size]
            insert_stmt = pg_insert(MagicBotoCardTagModel).values(
                [{"tag_id": tag_row.id, "oracle_id": oid} for oid in chunk]
            )
            stmt = insert_stmt.on_conflict_do_nothing(index_elements=["tag_id", "oracle_id"])
            await session.execute(stmt)
        return True

    async def sample_cards_for_tag(
        self,
        session: AsyncSession,
        tag_name: str,
        limit: int,
    ) -> list[MagicBotoCardModel]:
        """Return up to `limit` randomly sampled cards for the given tag.

        Returns an empty list if the tag does not exist or has no cards.
        One card per oracle_id; preserves the random ordering.
        """
        canonical = _canonical_tag_name(tag_name)
        tag_row = await session.scalar(
            select(MagicBotoTagModel).where(MagicBotoTagModel.name == canonical)
        )
        if tag_row is None:
            return []

        oracle_ids = (
            (
                await session.execute(
                    select(MagicBotoCardTagModel.oracle_id)
                    .where(MagicBotoCardTagModel.tag_id == tag_row.id)
                    .order_by(func.random())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        if not oracle_ids:
            return []

        all_cards = (
            (
                await session.execute(
                    select(MagicBotoCardModel)
                    .where(MagicBotoCardModel.oracle_id.in_(oracle_ids))
                    .order_by(MagicBotoCardModel.oracle_id, MagicBotoCardModel.card_id)
                )
            )
            .scalars()
            .all()
        )

        seen: dict[str, MagicBotoCardModel] = {}
        for card in all_cards:
            if card.oracle_id not in seen:
                seen[card.oracle_id] = card
        return [seen[oid] for oid in oracle_ids if oid in seen]

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
            )
            .scalars()
            .all()
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
