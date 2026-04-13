"""Parse inventory CSV files into row models."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CsvInventoryRow:
    """One CSV inventory row with Scryfall id and count."""

    scryfall_id: str
    count: int


class CsvParser:
    """Parse inventory CSV rows from disk or raw text."""

    def parse(self, csv_path: Path) -> Sequence[CsvInventoryRow]:
        if not csv_path.exists():
            raise ValueError(f"CSV file not found: {csv_path}")

        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            return self._parse_reader(csv.DictReader(handle))

    def parse_content(self, content: str) -> Sequence[CsvInventoryRow]:
        """Parse rows from a UTF-8 string (e.g. uploaded file text)."""
        text = content.lstrip("\ufeff")  # strip BOM if present
        return self._parse_reader(csv.DictReader(io.StringIO(text, newline="")))

    def _parse_reader(self, reader: csv.DictReader) -> Sequence[CsvInventoryRow]:  # type: ignore[type-arg]
        if not reader.fieldnames:
            raise ValueError("CSV has no header row.")
        column_map = self._normalized_column_map(
            {name: None for name in reader.fieldnames if name is not None}
        )
        # Prefer explicit Scryfall headers; plain "ID" / "id" is a common export alias.
        scryfall_key = column_map.get("scryfall id") or column_map.get("id")
        # Optional: "count" / "quantity". If absent or blank in a row, quantity defaults to 1.
        count_key = column_map.get("count") or column_map.get("quantity")
        if scryfall_key is None:
            raise ValueError(
                "CSV must include a Scryfall id column (e.g. 'scryfall id', 'SCRYFALL_ID', "
                "'id'). Optional: 'count' or 'quantity' (defaults to 1 per row if omitted or "
                "empty)."
            )

        rows: list[CsvInventoryRow] = []
        for index, row in enumerate(reader, start=2):
            scryfall_id = (row.get(scryfall_key) or "").strip().lower()
            if not scryfall_id:
                continue
            if count_key is None:
                count = 1
            else:
                count_text = (row.get(count_key) or "").strip()
                if not count_text:
                    count = 1
                else:
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
    def _canonical_header_name(header: str) -> str:
        """Lowercase header; strip BOM; treat ``_`` and ``-`` as spaces; collapse whitespace."""
        raw = header.strip().replace("\ufeff", "").strip()
        folded = raw.lower().replace("_", " ").replace("-", " ")
        return " ".join(folded.split())

    @staticmethod
    def _normalized_column_map(row: Mapping[str, str | None]) -> Mapping[str, str]:
        """Map canonical header names to the CSV's original column keys."""
        normalized: dict[str, str] = {}
        for key in row.keys():
            canonical = CsvParser._canonical_header_name(key)
            normalized[canonical] = key
        return normalized
