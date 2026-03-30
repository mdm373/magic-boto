"""Oracle tag sweep: track per-tag sweep progress for bot-driven card tagging."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import InvalidRequestError, NotFoundError
from app.models.magic_boto_card import MagicBotoCardModel
from app.models.magic_boto_oracle_tag_sweep import MagicBotoOracleTagSweepModel


def _canonical_tag_name(name: str) -> str:
    return name.strip().lower()


@dataclass(frozen=True)
class SweepPage:
    """Result of a single sweep page fetch."""

    cards: Sequence[MagicBotoCardModel]
    next_cursor: str | None
    is_complete: bool


class OracleTagSweepService:
    """Manage per-tag sweep state for incremental oracle-id tagging."""

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
        oracle_id_stmt = (
            select(MagicBotoCardModel.oracle_id)
            .group_by(MagicBotoCardModel.oracle_id)
            .order_by(MagicBotoCardModel.oracle_id)
            .limit(limit)
        )
        if cursor is not None:
            oracle_id_stmt = oracle_id_stmt.where(MagicBotoCardModel.oracle_id > cursor)
        if last_swept_at is not None:
            oracle_id_stmt = oracle_id_stmt.having(
                func.min(MagicBotoCardModel.created_at) > last_swept_at
            )

        pending_oracle_ids: list[str] = list(
            (await session.execute(oracle_id_stmt)).scalars().all()
        )

        if not pending_oracle_ids:
            return SweepPage(cards=(), next_cursor=None, is_complete=True)

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
        )

    async def start_sweep(
        self,
        session: AsyncSession,
        tag_name: str,
        limit: int = 50,
    ) -> SweepPage:
        """Create a new sweep row and return the first page of pending cards.

        Raises InvalidRequestError if a sweep already exists for this tag.
        Does not commit; caller owns the transaction.
        """
        canonical = _canonical_tag_name(tag_name)
        existing = await session.get(MagicBotoOracleTagSweepModel, canonical)
        if existing is not None:
            raise InvalidRequestError(
                f"A sweep already exists for tag '{canonical}'. Use resume_tagging to continue."
            )
        session.add(MagicBotoOracleTagSweepModel(tag_name=canonical))
        await session.flush()
        return await self._fetch_page(session, None, None, limit)

    async def resume_sweep(
        self,
        session: AsyncSession,
        tag_name: str,
        limit: int = 50,
    ) -> SweepPage:
        """Load an existing sweep and return the next page from the stored cursor.

        Raises NotFoundError if no sweep exists for this tag.
        Does not commit; caller owns the transaction.
        """
        canonical = _canonical_tag_name(tag_name)
        sweep = await session.get(MagicBotoOracleTagSweepModel, canonical)
        if sweep is None:
            raise NotFoundError(
                f"No sweep found for tag '{canonical}'. Use start_tagging to begin."
            )
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
        canonical = _canonical_tag_name(tag_name)
        sweep = await session.get(MagicBotoOracleTagSweepModel, canonical)
        if sweep is None:
            raise NotFoundError(f"No sweep found for tag '{canonical}'.")

        # Persist the cursor before fetching so a dropped bot resumes from here.
        await session.execute(
            update(MagicBotoOracleTagSweepModel)
            .where(MagicBotoOracleTagSweepModel.tag_name == canonical)
            .values(cursor=cursor)
        )

        page = await self._fetch_page(session, sweep.last_swept_at, cursor, limit)

        if page.is_complete:
            await session.execute(
                update(MagicBotoOracleTagSweepModel)
                .where(MagicBotoOracleTagSweepModel.tag_name == canonical)
                .values(last_swept_at=datetime.now(UTC), cursor=None)
            )

        return page

    async def reset_sweep(self, session: AsyncSession, tag_name: str) -> None:
        """Clear last_swept_at and cursor, forcing a full re-sweep on next resume.

        Raises NotFoundError if no sweep exists for this tag.
        Does not commit; caller owns the transaction.
        """
        canonical = _canonical_tag_name(tag_name)
        result: CursorResult[Any] = await session.execute(  # type: ignore[assignment]
            update(MagicBotoOracleTagSweepModel)
            .where(MagicBotoOracleTagSweepModel.tag_name == canonical)
            .values(last_swept_at=None, cursor=None)
        )
        if (result.rowcount or 0) == 0:
            raise NotFoundError(f"No sweep found for tag '{canonical}'.")
