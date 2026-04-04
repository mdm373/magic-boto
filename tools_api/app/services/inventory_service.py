"""Inventory service: orchestrates inventory business logic via InventoryRepo."""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import InvalidRequestError, NotFoundError
from app.models import InventoryModel
from app.repository.card_repo import CardRepo
from app.repository.inventory_repo import InventoryRepo

_repo = InventoryRepo()
_card_repo = CardRepo()


class InventoryService:
    """Orchestrates inventory business logic."""

    async def add_cards_from_scryfall_quantities(
        self,
        session: AsyncSession,
        inventory_id: uuid.UUID,
        quantities: Mapping[str, int],
        *,
        skip_unknown_scryfall_ids: bool = False,
    ) -> list[str]:
        """Resolve Scryfall IDs, validate, then upsert inventory rows. Caller must commit."""
        cleaned = self._clean_quantities(quantities)
        await self._ensure_exists(session, inventory_id)

        distinct_ids = list(cleaned.keys())
        scryfall_to_card_id = await _card_repo.resolve_scryfall_ids(session,distinct_ids)

        missing = [sid for sid in distinct_ids if sid not in scryfall_to_card_id]
        if not skip_unknown_scryfall_ids and missing:
            preview = missing[:10]
            suffix = f" (+{len(missing) - 10} more)" if len(missing) > 10 else ""
            raise InvalidRequestError(f"Unknown scryfall id: {preview}{suffix}")

        ignored = sorted(missing) if skip_unknown_scryfall_ids else []
        cleaned_known = (
            {k: v for k, v in cleaned.items() if k in scryfall_to_card_id}
            if skip_unknown_scryfall_ids
            else cleaned
        )
        if not cleaned_known:
            return ignored

        by_card_id: dict[str, int] = {}
        for sid, qty in cleaned_known.items():
            cid = scryfall_to_card_id[sid]
            by_card_id[cid] = by_card_id.get(cid, 0) + qty

        await _repo.upsert_card_counts(session, inventory_id, by_card_id)
        return ignored

    async def add_cards_by_scryfall_ids(
        self,
        session: AsyncSession,
        inventory_id: uuid.UUID,
        scryfall_ids: Sequence[str],
    ) -> None:
        """Add one copy per list element. Caller must commit."""
        counts = Counter(s for s in (x.strip() for x in scryfall_ids) if s)
        if not counts:
            return
        _ = await self.add_cards_from_scryfall_quantities(session, inventory_id, dict(counts))

    async def remove_cards_by_scryfall_ids(
        self,
        session: AsyncSession,
        inventory_id: uuid.UUID,
        scryfall_ids: Sequence[str],
    ) -> None:
        """Decrement counts; rows reaching zero are removed. Caller must commit."""
        counts = Counter(s for s in (x.strip() for x in scryfall_ids) if s)
        if not counts:
            return
        await self._ensure_exists(session, inventory_id)

        distinct_ids = list(counts.keys())
        resolved_map = await _card_repo.resolve_scryfall_ids(session,distinct_ids)

        missing = [k for k in counts if k not in resolved_map]
        if missing:
            preview = missing[:10]
            suffix = f" (+{len(missing) - 10} more)" if len(missing) > 10 else ""
            raise InvalidRequestError(f"Unknown scryfall id: {preview}{suffix}")

        by_card: dict[str, int] = {}
        for raw_id, qty in counts.items():
            cid = resolved_map[raw_id]
            by_card[cid] = by_card.get(cid, 0) + qty

        await _repo.decrement_card_counts(session, inventory_id, by_card)

    @staticmethod
    def _clean_quantities(raw: Mapping[str, int]) -> dict[str, int]:
        cleaned: dict[str, int] = {}
        for scryfall_id, count in raw.items():
            sid = scryfall_id.strip()
            if not sid or count <= 0:
                continue
            cleaned[sid] = cleaned.get(sid, 0) + count
        if not cleaned:
            raise InvalidRequestError(
                "Provide at least one non-empty scryfall id with count > 0"
            )
        return cleaned

    async def _ensure_exists(
        self,
        session: AsyncSession,
        inventory_id: uuid.UUID,
    ) -> None:
        exists = await session.scalar(
            select(InventoryModel.id).where(InventoryModel.id == inventory_id)
        )
        if exists is None:
            raise NotFoundError("Inventory not found")
