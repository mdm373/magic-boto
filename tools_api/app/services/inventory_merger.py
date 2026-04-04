"""Merge imported inventory rows by Scryfall id."""

from __future__ import annotations

from collections.abc import Sequence

from .inventory_csv_parser import CsvInventoryRow


class CsvInventoryRowMerger:
    """Aggregate row counts by Scryfall id."""

    def merge_counts(self, rows: Sequence[CsvInventoryRow]) -> Sequence[CsvInventoryRow]:
        """One row per Scryfall id with counts summed (order: first-seen id order)."""
        merged: dict[str, int] = {}
        for row in rows:
            merged[row.scryfall_id] = merged.get(row.scryfall_id, 0) + row.count
        return [CsvInventoryRow(scryfall_id=sid, count=count) for sid, count in merged.items()]
