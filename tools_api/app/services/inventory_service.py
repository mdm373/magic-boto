"""Inventory CRUD: named collections linked to ``magic_boto.cards`` via Scryfall printing id."""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import InvalidRequestError, NotFoundError
from app.inventory.names import canonical_inventory_name
from app.models import MagicBotoCardModel, MagicBotoInventoryCardModel, MagicBotoInventoryModel

_SCRYFALL_RESOLVE_BATCH_SIZE = 500
_INVENTORY_CARD_LOOKUP_BATCH_SIZE = 500


@dataclass(frozen=True, slots=True)
class _ResolvedInventoryAddCards:
    """Quantities per Scryfall printing id with resolved MTGJSON ``card_id`` per id."""

    quantities: Mapping[str, int]
    scryfall_to_card_id: Mapping[str, str]


class InventoryService:
    """Create/delete inventories; add cards by Scryfall printing id(s)."""

    async def list_inventory_names(self, session: AsyncSession) -> list[str]:
        """Return all inventory ``name`` values (canonical lowercase), sorted."""
        stmt = select(MagicBotoInventoryModel.name).order_by(MagicBotoInventoryModel.name.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_inventory_by_name(
        self,
        session: AsyncSession,
        name: str,
    ) -> MagicBotoInventoryModel | None:
        """Return an inventory by canonical name (trim + lowercase), if present."""
        normalized_name = canonical_inventory_name(name)
        stmt = select(MagicBotoInventoryModel).where(
            MagicBotoInventoryModel.name == normalized_name
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_inventory(
        self,
        session: AsyncSession,
        name: str,
    ) -> MagicBotoInventoryModel:
        """Return an inventory by name, creating it when missing."""
        existing = await self.get_inventory_by_name(session, name)
        if existing is not None:
            return existing
        return await self.create_inventory(session, name)

    async def create_inventory(
        self,
        session: AsyncSession,
        name: str,
    ) -> MagicBotoInventoryModel:
        """Insert inventory row; does not commit (caller owns the transaction)."""
        inv = MagicBotoInventoryModel(name=canonical_inventory_name(name))
        session.add(inv)
        await session.flush()
        await session.refresh(inv)
        return inv

    async def delete_inventory(self, session: AsyncSession, inventory_id: uuid.UUID) -> bool:
        stmt = delete(MagicBotoInventoryModel).where(MagicBotoInventoryModel.id == inventory_id)
        result = cast(CursorResult[Any], await session.execute(stmt))
        await session.commit()
        return (result.rowcount or 0) > 0

    async def add_cards_from_scryfall_quantities(
        self,
        session: AsyncSession,
        inventory_id: uuid.UUID,
        quantities: Mapping[str, int],
        *,
        skip_unknown_scryfall_ids: bool = False,
    ) -> list[str]:
        """Resolve Scryfall ids, then upsert inventory rows (same transaction; no commit).

        When ``skip_unknown_scryfall_ids`` is false (default), unknown ids raise
        ``InvalidRequestError``. When true, those ids are skipped and their Scryfall id
        strings are returned (sorted), with no exception.
        """
        cleaned = self._clean_quantities(quantities)
        await self._ensure_inventory_exists(session, inventory_id)
        distinct_ids = list(cleaned.keys())
        scryfall_to_card_id = await self._resolve_scryfall_ids_batched(session, distinct_ids)
        missing = [cid for cid in distinct_ids if cid not in scryfall_to_card_id]
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

        resolved_map = {k: scryfall_to_card_id[k] for k in cleaned_known}
        resolved = _ResolvedInventoryAddCards(
            quantities=cleaned_known,
            scryfall_to_card_id=resolved_map,
        )
        await self.add_cards_by_card_id(session, inventory_id, resolved)
        return ignored

    async def add_cards_by_card_id(
        self,
        session: AsyncSession,
        inventory_id: uuid.UUID,
        resolved: _ResolvedInventoryAddCards,
    ) -> None:
        """Upsert ``inventory_cards`` rows; increments are atomic (PostgreSQL ON CONFLICT)."""
        by_card_id: dict[str, int] = {}
        for sid, qty in resolved.quantities.items():
            cid = resolved.scryfall_to_card_id[sid]
            by_card_id[cid] = by_card_id.get(cid, 0) + qty

        if not by_card_id:
            return

        items = list(by_card_id.items())
        for i in range(0, len(items), _INVENTORY_CARD_LOOKUP_BATCH_SIZE):
            chunk = items[i : i + _INVENTORY_CARD_LOOKUP_BATCH_SIZE]
            rows = [
                {"inventory_id": inventory_id, "card_id": cid, "count": qty} for cid, qty in chunk
            ]
            insert_stmt = pg_insert(MagicBotoInventoryCardModel).values(rows)
            upsert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=[
                    MagicBotoInventoryCardModel.inventory_id,
                    MagicBotoInventoryCardModel.card_id,
                ],
                set_={
                    "count": MagicBotoInventoryCardModel.count + insert_stmt.excluded.count,
                },
            )
            await session.execute(upsert_stmt)

    async def add_cards_by_scryfall_ids(
        self,
        session: AsyncSession,
        inventory_id: uuid.UUID,
        scryfall_ids: Sequence[str],
    ) -> None:
        """Add quantities from Scryfall printing ids (each list element is one copy)."""
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
        """Decrement counts; rows with count 0 are removed. Unknown Scryfall ids are rejected."""
        counts = Counter(s for s in (x.strip() for x in scryfall_ids) if s)
        if not counts:
            return
        await self._ensure_inventory_exists(session, inventory_id)
        distinct_ids = list(counts.keys())
        resolved_map = await self._resolve_scryfall_ids_batched(session, distinct_ids)
        missing = [k for k in counts if k not in resolved_map]
        if missing:
            preview = missing[:10]
            suffix = f" (+{len(missing) - 10} more)" if len(missing) > 10 else ""
            raise InvalidRequestError(f"Unknown scryfall id: {preview}{suffix}")
        by_card: dict[str, int] = {}
        for raw_id, qty in counts.items():
            cid = resolved_map[raw_id]
            by_card[cid] = by_card.get(cid, 0) + qty
        for card_id, qty in by_card.items():
            # Delete rows that would hit zero or below (avoids violating count >= 1 constraint).
            await session.execute(
                delete(MagicBotoInventoryCardModel).where(
                    MagicBotoInventoryCardModel.inventory_id == inventory_id,
                    MagicBotoInventoryCardModel.card_id == card_id,
                    MagicBotoInventoryCardModel.count <= qty,
                )
            )
            # Decrement rows that still have count remaining.
            await session.execute(
                update(MagicBotoInventoryCardModel)
                .where(
                    MagicBotoInventoryCardModel.inventory_id == inventory_id,
                    MagicBotoInventoryCardModel.card_id == card_id,
                    MagicBotoInventoryCardModel.count > qty,
                )
                .values(count=MagicBotoInventoryCardModel.count - qty)
            )

    async def _ensure_inventory_exists(
        self,
        session: AsyncSession,
        inventory_id: uuid.UUID,
    ) -> None:
        inv_exists = await session.scalar(
            select(MagicBotoInventoryModel.id).where(MagicBotoInventoryModel.id == inventory_id),
        )
        if inv_exists is None:
            raise NotFoundError("Inventory not found")

    async def _resolve_scryfall_ids_batched(
        self,
        session: AsyncSession,
        scryfall_ids: list[str],
    ) -> dict[str, str]:
        out: dict[str, str] = {}
        for i in range(0, len(scryfall_ids), _SCRYFALL_RESOLVE_BATCH_SIZE):
            chunk = scryfall_ids[i : i + _SCRYFALL_RESOLVE_BATCH_SIZE]
            stmt = select(MagicBotoCardModel.scryfall_id, MagicBotoCardModel.card_id).where(
                MagicBotoCardModel.scryfall_id.in_(chunk),
                MagicBotoCardModel.scryfall_id.is_not(None),
            )
            rows = (await session.execute(stmt)).all()
            for row in rows:
                assert row.scryfall_id is not None and row.card_id is not None
                out[row.scryfall_id] = row.card_id
        return out

    @staticmethod
    def _clean_quantities(raw: Mapping[str, int]) -> dict[str, int]:
        cleaned: dict[str, int] = {}
        for scryfall_id, count in raw.items():
            sid = scryfall_id.strip()
            if not sid:
                continue
            if count <= 0:
                continue
            cleaned[sid] = cleaned.get(sid, 0) + count
        if not cleaned:
            raise InvalidRequestError("Provide at least one non-empty scryfall id with count > 0")
        return cleaned
