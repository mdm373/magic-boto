"""Inventory CRUD: named collections linked to mtgjson.cards via Scryfall printing id."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InventoryCardModel, InventoryModel
from app.schema.inventory_schema import InventoryResponse
from app.validators import ResolvedInventoryAddCards


class InventoryService:
    """Create/delete inventories; add cards by Scryfall printing id(s)."""

    async def create_inventory(
        self,
        session: AsyncSession,
        name: str,
    ) -> InventoryResponse:
        inv = InventoryModel(name=name.strip())
        session.add(inv)
        await session.commit()
        await session.refresh(inv)
        return InventoryResponse(id=inv.id, name=inv.name)

    async def delete_inventory(self, session: AsyncSession, inventory_id: uuid.UUID) -> bool:
        stmt = delete(InventoryModel).where(InventoryModel.id == inventory_id)
        result = cast(CursorResult[Any], await session.execute(stmt))
        await session.commit()
        return (result.rowcount or 0) > 0

    async def add_cards_by_card_id(
        self,
        session: AsyncSession,
        inventory_id: uuid.UUID,
        resolved: ResolvedInventoryAddCards,
    ) -> None:
        """
        Persist inventory rows. `resolved` comes from route-level validation only.
        """
        by_card_uuid: dict[str, int] = {}
        for sid, qty in resolved.quantities.items():
            card_uuid = resolved.scryfall_to_card_uuid[sid]
            by_card_uuid[card_uuid] = by_card_uuid.get(card_uuid, 0) + qty

        if not by_card_uuid:
            return

        card_uuids = list(by_card_uuid.keys())
        stmt = select(InventoryCardModel).where(
            InventoryCardModel.inventory_id == inventory_id,
            InventoryCardModel.card_uuid.in_(card_uuids),
        )
        result = await session.execute(stmt)
        existing: dict[str, InventoryCardModel] = {
            row.card_uuid: row for row in result.scalars().all()
        }

        for card_uuid, qty in by_card_uuid.items():
            row = existing.get(card_uuid)
            if row is not None:
                row.count += qty
            else:
                session.add(
                    InventoryCardModel(
                        inventory_id=inventory_id,
                        card_uuid=card_uuid,
                        count=qty,
                    ),
                )

        await session.commit()
