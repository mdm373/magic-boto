"""Inventory request validators."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import InvalidRequestError, NotFoundError
from app.models import MagicBotoCardModel, MagicBotoInventoryModel
from app.schema import AddInventoryCardsRequest


@dataclass(frozen=True, slots=True)
class ResolvedInventoryAddCards:
    """Validated add-cards payload: quantities per Scryfall id + resolved MTGJSON card ids."""

    quantities: Mapping[str, int]
    scryfall_to_card_id: Mapping[str, str]


class InventoryCardsValidator:
    """Validation helpers for inventory endpoints."""

    async def validate_add_inventory_cards(
        self,
        session: AsyncSession,
        cards: AddInventoryCardsRequest,
    ) -> ResolvedInventoryAddCards:
        """
        Normalize ids, ensure inventory exists, resolve Scryfall ids to printing rows.

        Raises InvalidRequestError if any Scryfall id is unknown in our DB.
        """
        normalized = self._normalize_scryfall_ids(cards)
        quantities = self._quantities(normalized)

        inv_exists = await session.scalar(
            select(MagicBotoInventoryModel.id).where(
                MagicBotoInventoryModel.id == cards.inventory_id
            ),
        )
        if inv_exists is None:
            raise NotFoundError("Inventory not found")

        distinct_ids = list(quantities.keys())
        stmt = select(MagicBotoCardModel.scryfall_id, MagicBotoCardModel.card_id).where(
            MagicBotoCardModel.scryfall_id.in_(distinct_ids),
            MagicBotoCardModel.scryfall_id.is_not(None),
        )
        rows = (await session.execute(stmt)).all()
        scryfall_to_card_id: dict[str, str] = {}
        for row in rows:
            assert row.scryfall_id is not None and row.card_id is not None
            scryfall_to_card_id[row.scryfall_id] = row.card_id

        missing = [cid for cid in distinct_ids if cid not in scryfall_to_card_id]
        if missing:
            preview = missing[:10]
            suffix = f" (+{len(missing) - 10} more)" if len(missing) > 10 else ""
            raise InvalidRequestError(f"Unknown scryfall id: {preview}{suffix}")

        return ResolvedInventoryAddCards(
            quantities=quantities,
            scryfall_to_card_id=scryfall_to_card_id,
        )

    @staticmethod
    def _normalize_scryfall_ids(cards: AddInventoryCardsRequest) -> list[str]:
        stripped = [sid.strip() for sid in cards.scryfall_ids if sid and sid.strip()]
        if not stripped:
            raise InvalidRequestError("Provide at least one non-empty scryfall id")
        return stripped

    @staticmethod
    def _quantities(normalized_ids: list[str]) -> dict[str, int]:
        quantities: dict[str, int] = {}
        for sid in normalized_ids:
            quantities[sid] = quantities.get(sid, 0) + 1
        return quantities
