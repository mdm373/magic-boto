"""Color identity pip symbols (WUBRG) for Commander-style identity."""

from __future__ import annotations

from enum import StrEnum


class ColorIdentity(StrEnum):
    """Single pip in a card's color identity (MTGJSON ``colorIdentity``)."""

    W = "W"  # white
    U = "U"  # blue
    B = "B"  # black
    R = "R"  # red
    G = "G"  # green


_WUBRG_ORDER = "WUBRG"


def normalize_color_identity_string(raw: list[str] | tuple[str, ...] | None) -> str:
    """
    Canonical DB string: unique pips in WUBRG order (e.g. ``\"BG\"``, ``\"R\"``, ``\"\"``).
    """

    if not raw:
        return ""
    seen: set[str] = set()
    for item in raw:
        c = str(item).strip().upper()
        if len(c) == 1 and c in _WUBRG_ORDER:
            seen.add(c)
    return "".join(sorted(seen, key=lambda x: _WUBRG_ORDER.index(x)))


def color_identity_string_to_list(s: str | None) -> list[ColorIdentity]:
    """Parse stored string into enum list (WUBRG order; ignores invalid/extra chars)."""

    if not s:
        return []
    out: list[ColorIdentity] = []
    for c in _WUBRG_ORDER:
        if c in s:
            out.append(ColorIdentity(c))
    return out
