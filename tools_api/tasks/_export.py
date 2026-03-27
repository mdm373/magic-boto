"""Inventory export task wrapper."""

from __future__ import annotations

import subprocess

from invoke import Collection, Context, Exit, task

from .constants import DEFAULT_INVENTORY_NAME


@task(default=True)
def export_inventory(c: Context) -> None:
    """Prompt for inventory name and print lines to the console (not allowed for ``_default``)."""

    inventory_name = input("Inventory name: ").strip()
    if not inventory_name:
        raise Exit("Inventory name is required.")

    if inventory_name.strip().lower() == DEFAULT_INVENTORY_NAME:
        raise Exit(
            f"Export is not allowed for the reserved default inventory {DEFAULT_INVENTORY_NAME!r}."
        )

    argv = [
        "uv",
        "run",
        "python",
        "-m",
        "app.inventory.export.main",
        inventory_name,
    ]
    if c.cwd:
        subprocess.run(argv, check=True, cwd=c.cwd)
    else:
        subprocess.run(argv, check=True)


ns = Collection("export")
ns.add_task(export_inventory, name="inventory")
