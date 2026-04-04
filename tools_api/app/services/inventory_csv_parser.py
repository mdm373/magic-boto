"""Parse inventory CSV files into row models."""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CsvInventoryRow:
    """One CSV inventory row with Scryfall id and count."""

    scryfall_id: str
    count: int


class CsvParser:
    """Parse inventory CSV rows from disk."""

    def parse(self, csv_path: Path) -> Sequence[CsvInventoryRow]:
        if not csv_path.exists():
            raise ValueError(f"CSV file not found: {csv_path}")

        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("CSV has no header row.")
            column_map = self._normalized_column_map({name: None for name in reader.fieldnames})
            scryfall_key = column_map.get("scryfall id")
            count_key = column_map.get("count")
            if scryfall_key is None or count_key is None:
                raise ValueError("CSV must include 'scryfall id' and 'count' columns.")

            rows: list[CsvInventoryRow] = []
            for index, row in enumerate(reader, start=2):
                scryfall_id = (row.get(scryfall_key) or "").strip()
                count_text = (row.get(count_key) or "").strip()
                if not scryfall_id:
                    continue
                if not count_text:
                    raise ValueError(
                        f"Missing count at row {index} for scryfall id '{scryfall_id}'."
                    )
                try:
                    count = int(count_text)
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid count '{count_text}' at row {index} for scryfall id "
                        f"'{scryfall_id}'."
                    ) from exc
                if count <= 0:
                    continue
                rows.append(CsvInventoryRow(scryfall_id=scryfall_id, count=count))

        if not rows:
            raise ValueError("CSV contains no importable rows with count > 0.")
        return rows

    @staticmethod
    def _normalized_column_map(row: Mapping[str, str | None]) -> Mapping[str, str]:
        """Normalize column names to lowercase and collapse whitespace."""
        normalized: dict[str, str] = {}
        for key in row.keys():
            canonical = " ".join(key.strip().lower().split())
            normalized[canonical] = key
        return normalized
