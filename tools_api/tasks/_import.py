"""Inventory task wrappers."""

from __future__ import annotations

import subprocess

from invoke import Collection, Context, Exit, task

from .constants import DEFAULT_INVENTORY_NAME

# Map Unicode smart punctuation to ASCII so we can peel a matching outer pair.
# (No standard library “unquote” for paths; shlex/ast.literal_eval are wrong here—
# shlex splits on spaces in unquoted paths; literal_eval treats \\ as escapes in Python.)
_SMART_TO_ASCII_QUOTES = str.maketrans(
    {
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
    }
)


def _strip_wrapping_quotes(s: str) -> str:
    """Normalize pasted smart quotes, then remove outer matching ``"`` or ``'`` pairs."""
    t = s.strip().translate(_SMART_TO_ASCII_QUOTES)
    while len(t) >= 2 and t[0] == t[-1] and t[0] in {'"', "'"}:
        t = t[1:-1].strip()
    return t


@task(default=True)
def import_csv(c: Context) -> None:
    """Prompt for CSV path and inventory name, then import.

    Empty inventory name uses the reserved ``_default`` collection.
    """

    csv_path = _strip_wrapping_quotes(input("Path to CSV: "))
    if not csv_path:
        raise Exit("CSV path is required.")

    raw_name = input(f"Inventory name ({DEFAULT_INVENTORY_NAME}): ").strip()
    inventory_name = raw_name if raw_name else DEFAULT_INVENTORY_NAME

    argv = [
        "uv",
        "run",
        "python",
        "-m",
        "app.inventory.import.main",
        csv_path,
        inventory_name,
    ]
    if c.cwd:
        subprocess.run(argv, check=True, cwd=c.cwd)
    else:
        subprocess.run(argv, check=True)


ns = Collection("import")
ns.add_task(import_csv, name="inventory")
