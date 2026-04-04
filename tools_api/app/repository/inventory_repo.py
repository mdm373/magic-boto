"""Repository for ``magic_boto`` inventory tables."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InventoryCardModel, InventoryModel

from .canonical import canonical_name

_INVENTORY_CARD_LOOKUP_BATCH_SIZE = 500


class InventoryRepo:
    """Pure ORM access for ``magic_boto`` inventory tables."""

    async def list_names(self, session: AsyncSession) -> list[str]:
        """Return all inventory names (canonical lowercase), sorted."""
        result = await session.execute(
            select(InventoryModel.name).order_by(InventoryModel.name.asc())
        )
        return list(result.scalars().all())

    async def get_by_name(
        self,
        session: AsyncSession,
        name: str,
    ) -> InventoryModel | None:
        """Return an inventory by canonical name, if present."""
        result = await session.execute(
            select(InventoryModel).where(InventoryModel.name == canonical_name(name))
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        session: AsyncSession,
        name: str,
    ) -> InventoryModel:
        """Return an inventory by name, creating it when missing. Caller must commit."""
        existing = await self.get_by_name(session, name)
        if existing is not None:
            return existing
        return await self.create(session, name)

    async def create(
        self,
        session: AsyncSession,
        name: str,
    ) -> InventoryModel:
        """Insert inventory row. Caller must commit."""
        inv = InventoryModel(name=canonical_name(name))
        session.add(inv)
        await session.flush()
        await session.refresh(inv)
        return inv

    async def delete(self, session: AsyncSession, inventory_id: uuid.UUID) -> bool:
        """Delete inventory row. Caller must commit."""
        result = cast(
            CursorResult[Any],
            await session.execute(delete(InventoryModel).where(InventoryModel.id == inventory_id)),
        )
        return (result.rowcount or 0) > 0

    async def upsert_card_counts(
        self,
        session: AsyncSession,
        inventory_id: uuid.UUID,
        by_card_id: Mapping[str, int],
    ) -> None:
        """Upsert inventory_cards rows, incrementing existing counts. Caller must commit."""
        items = list(by_card_id.items())
        for i in range(0, len(items), _INVENTORY_CARD_LOOKUP_BATCH_SIZE):
            chunk = items[i : i + _INVENTORY_CARD_LOOKUP_BATCH_SIZE]
            rows = [
                {"inventory_id": inventory_id, "card_id": cid, "count": qty} for cid, qty in chunk
            ]
            insert_stmt = pg_insert(InventoryCardModel).values(rows)
            await session.execute(
                insert_stmt.on_conflict_do_update(
                    index_elements=[InventoryCardModel.inventory_id, InventoryCardModel.card_id],
                    set_={"count": InventoryCardModel.count + insert_stmt.excluded.count},
                )
            )

    async def decrement_card_counts(
        self,
        session: AsyncSession,
        inventory_id: uuid.UUID,
        by_card_id: Mapping[str, int],
    ) -> None:
        """Decrement inventory_cards counts; rows reaching zero are removed. Caller must commit."""
        for card_id, qty in by_card_id.items():
            await session.execute(
                delete(InventoryCardModel).where(
                    InventoryCardModel.inventory_id == inventory_id,
                    InventoryCardModel.card_id == card_id,
                    InventoryCardModel.count <= qty,
                )
            )
            await session.execute(
                update(InventoryCardModel)
                .where(
                    InventoryCardModel.inventory_id == inventory_id,
                    InventoryCardModel.card_id == card_id,
                    InventoryCardModel.count > qty,
                )
                .values(count=InventoryCardModel.count - qty)
            )
