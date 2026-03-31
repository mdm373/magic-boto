"""Inventory export task wrapper."""

from __future__ import annotations

import subprocess
from pathlib import Path

from invoke import Collection, Context, Exit, task

from .constants import DEFAULT_INVENTORY_NAME
from .pg_env import pg_env


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


@task()
def db_schema(c: Context) -> None:
    """Update tools_api/debug/schema.sql from the live DB (pg_dump -s)."""
    out_dir = Path("debug")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "schema.sql"

    env = pg_env()
    print(f"Dumping schema to: {out_path}")
    c.run(f'pg_dump -s -f "{out_path}"', env=env)


@task
def get_tag(c: Context, name: str = "") -> None:
    """Show a tag by name, or list all tags if no name is given."""
    argv = ["uv", "run", "python", "-m", "app.tag.get.main"]
    if name.strip():
        argv.append(name.strip())
    if c.cwd:
        subprocess.run(argv, check=True, cwd=c.cwd)
    else:
        subprocess.run(argv, check=True)


ns = Collection("export")
ns.add_task(export_inventory, name="inventory", default=True)
ns.add_task(db_schema, name="db-schema")
ns.add_task(get_tag, name="tag")
