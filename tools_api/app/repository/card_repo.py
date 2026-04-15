"""Repository for ``magic_boto.cards``."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import sqlalchemy as sa
from fastapi_pagination import Params
from fastapi_pagination.bases import AbstractPage
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import and_, func, select, true
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from app.models import CardModel, InventoryCardModel, InventoryModel

from .pg_bulk_upsert import orm_columns_dict

# asyncpg rejects queries whose total bind parameters exceed 32767; chunk IN lists.
_IN_CLAUSE_BATCH = 500


def _apply_ordering(
    stmt: Select[tuple[CardModel]], *, distinct_oracle: bool
) -> Select[tuple[CardModel]]:
    if distinct_oracle:
        return stmt.distinct(CardModel.oracle_id).order_by(
            CardModel.oracle_id.asc(),
            CardModel.name.asc(),
        )
    return stmt.order_by(CardModel.name.asc())


class CardRepo:
    """Pure ORM access for ``magic_boto.cards``."""

    async def search_cards(
        self,
        session: AsyncSession,
        *,
        filters: Sequence[ColumnElement[bool]],
        distinct_oracle: bool,
        page_number: int,
        page_size: int,
        inventory_name: str | None = None,
    ) -> AbstractPage[CardModel]:
        """Paginated card search. Returns a page of CardModel instances."""
        base = select(CardModel).options(
            selectinload(CardModel.card_types),
            selectinload(CardModel.subtypes),
            selectinload(CardModel.keywords),
            selectinload(CardModel.supertypes),
            selectinload(CardModel.meta),
        )
        if inventory_name is not None:
            base = base.join(
                InventoryCardModel,
                CardModel.card_id == InventoryCardModel.card_id,
            ).join(
                InventoryModel,
                and_(
                    InventoryModel.id == InventoryCardModel.inventory_id,
                    InventoryModel.name == inventory_name,
                ),
            )
        base = base.where(and_(*filters) if filters else true())
        stmt = _apply_ordering(base, distinct_oracle=distinct_oracle)
        return cast(
            AbstractPage[CardModel],
            await paginate(
                session,
                stmt,
                params=Params(page=page_number, size=page_size),
            ),
        )

    async def fetch_by_oracle_ids(
        self,
        session: AsyncSession,
        oracle_ids: Sequence[str],
    ) -> Sequence[CardModel]:
        """Return one representative card per oracle_id, preserving input order."""
        if not oracle_ids:
            return []
        ids = list(oracle_ids)
        by_oracle_id: dict[str, CardModel] = {}
        for i in range(0, len(ids), _IN_CLAUSE_BATCH):
            chunk = ids[i : i + _IN_CLAUSE_BATCH]
            if not chunk:
                continue
            unique_chunk = list(dict.fromkeys(chunk))
            rows = await session.execute(
                select(CardModel)
                .where(CardModel.oracle_id.in_(unique_chunk))
                .distinct(CardModel.oracle_id)
                .order_by(CardModel.oracle_id, CardModel.card_id)
            )
            for card in rows.scalars():
                by_oracle_id[card.oracle_id] = card
        return [by_oracle_id[oid] for oid in oracle_ids if oid in by_oracle_id]

    async def get_by_id(
        self,
        session: AsyncSession,
        card_id: str,
    ) -> CardModel | None:
        """Return a single card by primary key, with all relationships loaded."""
        stmt = (
            select(CardModel)
            .options(
                selectinload(CardModel.card_types),
                selectinload(CardModel.subtypes),
                selectinload(CardModel.keywords),
                selectinload(CardModel.supertypes),
                selectinload(CardModel.meta),
            )
            .where(CardModel.card_id == card_id)
        )
        result = await session.execute(stmt)
        return result.scalars().one_or_none()

    async def filter_known_oracle_ids(
        self,
        session: AsyncSession,
        oracle_ids: Sequence[str],
    ) -> frozenset[str]:
        """Return the subset of oracle_ids that exist in ``magic_boto.cards``."""
        ids = list(oracle_ids)
        known: set[str] = set()
        for i in range(0, len(ids), _IN_CLAUSE_BATCH):
            chunk = ids[i : i + _IN_CLAUSE_BATCH]
            if not chunk:
                continue
            unique_chunk = list(dict.fromkeys(chunk))
            result = await session.execute(
                select(CardModel.oracle_id).where(CardModel.oracle_id.in_(unique_chunk))
            )
            known.update(result.scalars().all())
        return frozenset(known)

    async def resolve_scryfall_ids(
        self,
        session: AsyncSession,
        scryfall_ids: Sequence[str],
    ) -> dict[str, str]:
        """Return a mapping of printing Scryfall id → ``card_id`` for known ids.

        Keys are ``strip().lower()`` so callers can match case-insensitively.
        ``cards.scryfall_id`` is non-null; ``DISTINCT ON`` picks one row per id when
        several share a printing id (e.g. double-faced ``a`` / ``b`` rows). Prefer
        ``(scryfall_id, side)`` when you need a specific catalog row.
        """
        out: dict[str, str] = {}
        ids = list(scryfall_ids)
        for i in range(0, len(ids), _IN_CLAUSE_BATCH):
            chunk = ids[i : i + _IN_CLAUSE_BATCH]
            chunk_norm = list(dict.fromkeys(s.strip().lower() for s in chunk if s and s.strip()))
            if not chunk_norm:
                continue
            sid_lower = func.lower(CardModel.scryfall_id)
            rows = (
                await session.execute(
                    select(CardModel.scryfall_id, CardModel.card_id)
                    .where(
                        sid_lower.in_(chunk_norm),
                    )
                    .distinct(sid_lower)
                    .order_by(sid_lower, CardModel.card_id)
                )
            ).all()
            for row in rows:
                assert row.scryfall_id is not None and row.card_id is not None
                out[row.scryfall_id.strip().lower()] = row.card_id
        return out

    async def insert_many(
        self,
        session: AsyncSession,
        rows: Sequence[CardModel],
        *,
        batch_size: int,
    ) -> None:
        """Bulk-insert cards; on ``(scryfall_id, side)`` conflict, update only when changed.

        - Never overwrite ``created_at``.
        - Never update ``card_id`` (PK) during a conflict update.
        - Set ``updated_at`` only when any tracked card fields are actually different.
        """
        if not rows:
            return

        param_rows = [orm_columns_dict(row) for row in rows]
        index_elements = ("scryfall_id", "side")

        for start in range(0, len(param_rows), batch_size):
            chunk = param_rows[start : start + batch_size]
            insert_stmt = pg_insert(CardModel).values(list(chunk))
            excluded = insert_stmt.excluded

            # Columns we will overwrite from EXCLUDED on conflict.
            # We intentionally skip PK `card_id` and timestamps.
            overwrite_cols: list[str] = [
                col.name
                for col in CardModel.__table__.columns
                if col.name not in {"card_id", "created_at", "updated_at"}
            ]
            set_ = {name: getattr(excluded, name) for name in overwrite_cols}
            set_["updated_at"] = func.now()

            # Only update when values actually differ. `IS DISTINCT FROM` treats NULL safely.
            where_changed = sa.or_(
                *[
                    getattr(CardModel, name).is_distinct_from(getattr(excluded, name))
                    for name in overwrite_cols
                ]
            )

            stmt = insert_stmt.on_conflict_do_update(
                index_elements=list(index_elements),
                set_=set_,
                where=where_changed,
            )
            await session.execute(stmt)
