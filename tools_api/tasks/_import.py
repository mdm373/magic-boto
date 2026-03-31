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


def _read_multiline(prompt: str) -> str:
    """Read lines until two consecutive blank lines (or EOF), preserving single blank lines.

    Handles pasted multi-paragraph text: a single blank line between paragraphs
    is kept; a second consecutive blank line signals end of input.
    Leading/trailing whitespace on each line is stripped; the result is trimmed.
    """
    print(prompt)
    lines: list[str] = []
    last_blank = False
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            if last_blank:
                break
            last_blank = True
            lines.append("")
        else:
            last_blank = False
            lines.append(line.strip())
    return "\n".join(lines).strip()


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


@task
def create_tag(c: Context) -> None:
    """Prompt for tag name and description, then create the tag."""
    name = input("Tag name: ").strip()
    if not name:
        raise Exit("Tag name is required.")

    description = _read_multiline("Tag description (two blank lines to finish):")
    if not description:
        raise Exit("Tag description is required.")

    argv = ["uv", "run", "python", "-m", "app.tag.create.main", name, description]
    if c.cwd:
        subprocess.run(argv, check=True, cwd=c.cwd)
    else:
        subprocess.run(argv, check=True)


@task
def rename_tag(c: Context, old_name: str = "", new_name: str = "") -> None:
    """Prompt for old and new tag names, then rename the tag and any _unsure/_excluded side tags."""
    if not old_name.strip():
        old_name = input("Current tag name: ").strip()
    if not old_name:
        raise Exit("Current tag name is required.")

    if not new_name.strip():
        new_name = input("New tag name: ").strip()
    if not new_name:
        raise Exit("New tag name is required.")

    argv = ["uv", "run", "python", "-m", "app.tag.rename.main", old_name, new_name]
    if c.cwd:
        subprocess.run(argv, check=True, cwd=c.cwd)
    else:
        subprocess.run(argv, check=True)


ns = Collection("import")
ns.add_task(import_csv, name="inventory")
ns.add_task(create_tag, name="tag")
ns.add_task(rename_tag, name="rename-tag")
