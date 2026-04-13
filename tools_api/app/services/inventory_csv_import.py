"""Load inventory rows from a CSV file path into an existing DB session."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import InvalidRequestError
from app.repository import InventoryRepo

from .inventory_csv_parser import CsvParser
from .inventory_merger import CsvInventoryRowMerger
from .inventory_service import InventoryService

_parser = CsvParser()
_merger = CsvInventoryRowMerger()


async def import_inventory_from_csv_path(
    session: AsyncSession,
    inventory_name: str,
    csv_path: Path,
) -> list[str]:
    """Parse ``csv_path``, upsert counts into ``inventory_name``. Returns unknown Scryfall ids."""
    inv_repo = InventoryRepo()
    service = InventoryService()
    try:
        parsed_rows = _parser.parse(csv_path)
    except ValueError as exc:
        raise InvalidRequestError(str(exc)) from exc

    merged_rows = _merger.merge_counts(parsed_rows)
    quantities = {r.scryfall_id: r.count for r in merged_rows}
    inv = await inv_repo.get_or_create(session, inventory_name)
    return await service.add_cards_from_scryfall_quantities(
        session,
        inv.id,
        quantities,
        skip_unknown_scryfall_ids=True,
    )


async def import_inventory_from_csv_content(
    session: AsyncSession,
    inventory_name: str,
    csv_content: str,
) -> list[str]:
    """Parse ``csv_content`` string, upsert counts into ``inventory_name``. Returns unknown ids."""
    inv_repo = InventoryRepo()
    service = InventoryService()
    try:
        parsed_rows = _parser.parse_content(csv_content)
    except ValueError as exc:
        raise InvalidRequestError(str(exc)) from exc

    merged_rows = _merger.merge_counts(parsed_rows)
    quantities = {r.scryfall_id: r.count for r in merged_rows}
    inv = await inv_repo.get_or_create(session, inventory_name)
    return await service.add_cards_from_scryfall_quantities(
        session,
        inv.id,
        quantities,
        skip_unknown_scryfall_ids=True,
    )
