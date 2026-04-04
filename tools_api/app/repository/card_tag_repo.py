"""Repository for ``magic_boto.card_tags`` (tag ↔ oracle_id junction)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CardTagModel
from settings import get_settings


@dataclass(frozen=True, slots=True)
class CardTagEntry:
    """A single card-tagging request: the oracle_id to tag."""

    oracle_id: str


class CardTagRepo:
    """Pure ORM access for ``magic_boto.card_tags``."""

    async def sample_oracle_ids(
        self,
        session: AsyncSession,
        tag_id: uuid.UUID,
        limit: int,
    ) -> Sequence[str]:
        """Return up to ``limit`` randomly sampled oracle_ids for a tag."""
        result = await session.execute(
            select(CardTagModel.oracle_id)
            .where(CardTagModel.tag_id == tag_id)
            .order_by(func.random())
            .limit(limit)
        )
        return result.scalars().all()

    async def upsert(
        self,
        session: AsyncSession,
        tag_id: object,
        oracle_ids: Sequence[str],
    ) -> None:
        """Insert tag→oracle_id rows, ignoring conflicts. Caller must commit."""
        chunk_size = get_settings().db_insert_chunk_size
        ids = list(oracle_ids)
        for i in range(0, len(ids), chunk_size):
            chunk = ids[i : i + chunk_size]
            stmt = pg_insert(CardTagModel).values(
                [{"tag_id": tag_id, "oracle_id": oid} for oid in chunk]
            )
            await session.execute(
                stmt.on_conflict_do_nothing(index_elements=["tag_id", "oracle_id"])
            )

    async def delete(
        self,
        session: AsyncSession,
        tag_id: object,
        oracle_ids: Sequence[str],
    ) -> None:
        """Remove tag→oracle_id rows. Caller must commit."""
        await session.execute(
            delete(CardTagModel).where(
                CardTagModel.tag_id == tag_id,
                CardTagModel.oracle_id.in_(list(oracle_ids)),
            )
        )

    async def delete_all_for_tag(self, session: AsyncSession, tag_id: object) -> int:
        """Remove all card_tag rows for a tag. Returns row count. Caller must commit."""
        result = cast(
            CursorResult[tuple[()]],
            await session.execute(delete(CardTagModel).where(CardTagModel.tag_id == tag_id)),
        )
        return result.rowcount or 0
