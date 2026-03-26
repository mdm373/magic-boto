"""Inventory CRUD: named collections linked to ``magic_boto.cards`` via Scryfall printing id."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MagicBotoInventoryCardModel, MagicBotoInventoryModel
from app.schema.inventory_schema import InventoryResponse
from app.validators import ResolvedInventoryAddCards


class InventoryService:
    """Create/delete inventories; add cards by Scryfall printing id(s)."""

    async def create_inventory(
        self,
        session: AsyncSession,
        name: str,
    ) -> InventoryResponse:
        inv = MagicBotoInventoryModel(name=name.strip())
        session.add(inv)
        await session.commit()
        await session.refresh(inv)
        return InventoryResponse(id=inv.id, name=inv.name)

    async def delete_inventory(self, session: AsyncSession, inventory_id: uuid.UUID) -> bool:
        stmt = delete(MagicBotoInventoryModel).where(MagicBotoInventoryModel.id == inventory_id)
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
        by_card_id: dict[str, int] = {}
        for sid, qty in resolved.quantities.items():
            cid = resolved.scryfall_to_card_id[sid]
            by_card_id[cid] = by_card_id.get(cid, 0) + qty

        if not by_card_id:
            return

        card_ids = list(by_card_id.keys())
        stmt = select(MagicBotoInventoryCardModel).where(
            MagicBotoInventoryCardModel.inventory_id == inventory_id,
            MagicBotoInventoryCardModel.card_id.in_(card_ids),
        )
        result = await session.execute(stmt)
        existing: dict[str, MagicBotoInventoryCardModel] = {
            row.card_id: row for row in result.scalars().all()
        }

        for card_id, qty in by_card_id.items():
            row = existing.get(card_id)
            if row is not None:
                row.count += qty
            else:
                session.add(
                    MagicBotoInventoryCardModel(
                        inventory_id=inventory_id,
                        card_id=card_id,
                        count=qty,
                    ),
                )

        await session.commit()
