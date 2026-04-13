"""CLI: import inventory rows from CSV (Scryfall id column; optional count/quantity, default 1)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from loguru import logger

from app.db import cli_session_scope
from app.log import configure_cli_logging
from app.repository import InventoryRepo
from app.services import CsvInventoryRowMerger, CsvParser, create_inventory_service
from settings import get_settings


def _parse_args() -> tuple[Path, str]:
    args = sys.argv[1:]
    if len(args) != 2:
        raise ValueError("Usage: python -m app.cmd.inventory.ingest <csv_path> <inventory_name>")
    return Path(args[0]), args[1]


parser = CsvParser()
merger = CsvInventoryRowMerger()
service = create_inventory_service()
_inv_repo = InventoryRepo()


async def _run(csv_path: Path, inventory_name: str) -> None:
    logger.info("Import: reading {} ...", csv_path)
    parsed_rows = parser.parse(csv_path)
    logger.info("Import: {} CSV row(s) with positive counts.", len(parsed_rows))

    merged_rows = merger.merge_counts(parsed_rows)
    total_copies = sum(r.count for r in merged_rows)
    logger.info(
        "Import: merged to {} unique Scryfall id(s) ({} total copies).",
        len(merged_rows),
        total_copies,
    )

    quantities = {r.scryfall_id: r.count for r in merged_rows}
    ignored: list[str] = []
    max_unknown = get_settings().inventory_import_max_unknown_scryfall_ids
    async with cli_session_scope() as session:
        inv = await _inv_repo.get_or_create(session, inventory_name)
        resolved_name = inv.name
        ignored = await service.add_cards_from_scryfall_quantities(
            session,
            inv.id,
            quantities,
            skip_unknown_scryfall_ids=True,
        )
        if ignored:
            logger.info("Import: {} Scryfall id(s) not in catalog:", len(ignored))
            logger.info("{}", ", ".join(ignored))
        if len(ignored) > max_unknown:
            logger.error(
                "Import: too many unknown Scryfall ids ({} > max allowed {}).",
                len(ignored),
                max_unknown,
            )
            sys.exit(1)

    skipped_copies = sum(quantities.get(sid, 0) for sid in ignored)
    saved_copies = total_copies - skipped_copies
    saved_unique = len(merged_rows) - len(ignored)
    logger.info(
        "Import: complete — {} card(s) across {} unique Scryfall id(s) saved to inventory {!r}.",
        saved_copies,
        saved_unique,
        resolved_name,
    )


def main() -> None:
    configure_cli_logging()
    csv_path, inventory_name = _parse_args()
    asyncio.run(_run(csv_path, inventory_name))


if __name__ == "__main__":
    main()
