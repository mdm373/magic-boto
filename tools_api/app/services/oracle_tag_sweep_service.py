"""Oracle tag sweep: track per-tag sweep progress for bot-driven card tagging."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.models.magic_boto_card import MagicBotoCardModel
from app.models.magic_boto_oracle_tag_sweep import MagicBotoOracleTagSweepModel
from app.models.magic_boto_tag import MagicBotoTagModel


def _canonical_tag_name(name: str) -> str:
    return name.strip().lower()


@dataclass(frozen=True)
class SweepPage:
    """Result of a single sweep page fetch."""

    cards: Sequence[MagicBotoCardModel]
    next_cursor: str | None
    is_complete: bool
    total_pending: int
    already_processed: int


class OracleTagSweepService:
    """Manage per-tag sweep state for incremental oracle-id tagging."""

    async def _resolve_tag_id(self, session: AsyncSession, tag_name: str) -> uuid.UUID:
        """Return the UUID for a tag name, raising NotFoundError if absent."""
        canonical = _canonical_tag_name(tag_name)
        tag_id: uuid.UUID | None = await session.scalar(
            select(MagicBotoTagModel.id).where(MagicBotoTagModel.name == canonical)
        )
        if tag_id is None:
            raise NotFoundError(f"Tag '{canonical}' not found.")
        return tag_id

    async def _fetch_page(
        self,
        session: AsyncSession,
        last_swept_at: datetime | None,
        cursor: str | None,
        limit: int,
    ) -> SweepPage:
        """Fetch one page of pending oracle_ids and return their representative cards.

        Uses MIN(created_at) per oracle_id to exclude reprints — a reprint's oracle_id
        has MIN(created_at) from before last_swept_at and is excluded. A new oracle_id
        has MIN(created_at) after last_swept_at and is included.
        """
        base_stmt = select(MagicBotoCardModel.oracle_id).group_by(MagicBotoCardModel.oracle_id)
        if last_swept_at is not None:
            base_stmt = base_stmt.having(func.min(MagicBotoCardModel.created_at) > last_swept_at)

        # Total pending (all oracle_ids not yet swept, regardless of cursor position).
        total_pending: int = (
            await session.scalar(select(func.count()).select_from(base_stmt.subquery()))
        ) or 0

        # Cards already processed in prior runs (oracle_ids up to and including cursor).
        already_processed: int = 0
        if cursor is not None:
            already_processed = (
                await session.scalar(
                    select(func.count()).select_from(
                        base_stmt.where(MagicBotoCardModel.oracle_id <= cursor).subquery()
                    )
                )
            ) or 0

        page_stmt = base_stmt.order_by(MagicBotoCardModel.oracle_id).limit(limit)
        if cursor is not None:
            page_stmt = page_stmt.where(MagicBotoCardModel.oracle_id > cursor)

        pending_oracle_ids: list[str] = list((await session.execute(page_stmt)).scalars().all())

        if not pending_oracle_ids:
            return SweepPage(
                cards=(),
                next_cursor=None,
                is_complete=True,
                total_pending=0,
                already_processed=total_pending,
            )

        # Load one card per oracle_id; selectin relationships populate all needed data.
        cards_stmt = (
            select(MagicBotoCardModel)
            .where(MagicBotoCardModel.oracle_id.in_(pending_oracle_ids))
            .order_by(MagicBotoCardModel.oracle_id, MagicBotoCardModel.card_id)
        )
        all_cards = (await session.execute(cards_stmt)).scalars().all()

        seen: dict[str, MagicBotoCardModel] = {}
        for card in all_cards:
            if card.oracle_id not in seen:
                seen[card.oracle_id] = card

        page = tuple(seen[oid] for oid in pending_oracle_ids if oid in seen)
        return SweepPage(
            cards=page,
            next_cursor=pending_oracle_ids[-1],
            is_complete=False,
            total_pending=total_pending,
            already_processed=already_processed,
        )

    async def resume_sweep(
        self,
        session: AsyncSession,
        tag_name: str,
        limit: int = 50,
    ) -> SweepPage:
        """Load or create a sweep record and return the next page from the stored cursor.

        Creates the sweep record if none exists (upsert).
        Does not commit; caller owns the transaction.
        """
        tag_id = await self._resolve_tag_id(session, tag_name)
        sweep = await session.get(MagicBotoOracleTagSweepModel, tag_id)
        if sweep is None:
            sweep = MagicBotoOracleTagSweepModel(tag_id=tag_id)
            session.add(sweep)
            await session.flush()
        return await self._fetch_page(session, sweep.last_swept_at, sweep.cursor, limit)

    async def advance_and_fetch(
        self,
        session: AsyncSession,
        tag_name: str,
        cursor: str | None,
        limit: int = 50,
    ) -> SweepPage:
        """Advance the cursor and fetch the next page.

        Persists the cursor before fetching so a dropped bot can resume from this point.
        If the next page is empty, marks the sweep complete (last_swept_at = now(),
        cursor = NULL).

        Raises NotFoundError if no sweep exists for this tag.
        Does not commit; caller owns the transaction.
        """
        tag_id = await self._resolve_tag_id(session, tag_name)
        sweep = await session.get(MagicBotoOracleTagSweepModel, tag_id)
        if sweep is None:
            raise NotFoundError(f"No sweep found for tag '{_canonical_tag_name(tag_name)}'.")

        # Persist the cursor before fetching so a dropped bot resumes from here.
        await session.execute(
            update(MagicBotoOracleTagSweepModel)
            .where(MagicBotoOracleTagSweepModel.tag_id == tag_id)
            .values(cursor=cursor)
        )

        page = await self._fetch_page(session, sweep.last_swept_at, cursor, limit)

        if page.is_complete:
            await session.execute(
                update(MagicBotoOracleTagSweepModel)
                .where(MagicBotoOracleTagSweepModel.tag_id == tag_id)
                .values(last_swept_at=datetime.now(UTC), cursor=None)
            )

        return page

    async def reset_sweep(self, session: AsyncSession, tag_name: str) -> None:
        """Clear last_swept_at and cursor, forcing a full re-sweep on next resume.

        Raises NotFoundError if no sweep exists for this tag.
        Does not commit; caller owns the transaction.
        """
        tag_id = await self._resolve_tag_id(session, tag_name)
        result: CursorResult[Any] = await session.execute(  # type: ignore[assignment]
            update(MagicBotoOracleTagSweepModel)
            .where(MagicBotoOracleTagSweepModel.tag_id == tag_id)
            .values(last_swept_at=None, cursor=None)
        )
        if (result.rowcount or 0) == 0:
            raise NotFoundError(f"No sweep found for tag '{_canonical_tag_name(tag_name)}'.")
