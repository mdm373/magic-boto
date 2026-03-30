"""Inventory delete task wrapper."""

from __future__ import annotations

import subprocess

from invoke import Collection, Context, Exit, task

from .constants import DEFAULT_INVENTORY_NAME


@task
def delete_inventory(c: Context) -> None:
    """Prompt for inventory name; confirm before deleting the reserved default inventory."""

    inventory_name = input("Inventory name to delete (trimmed/lowercased in DB): ").strip()
    if not inventory_name:
        raise Exit("Inventory name is required.")

    if inventory_name.strip().lower() == DEFAULT_INVENTORY_NAME:
        reply = input(
            f"You are about to delete the default inventory ({DEFAULT_INVENTORY_NAME!r}). "
            "Type 'yes' to confirm: "
        )
        if reply.strip().lower() != "yes":
            raise Exit("Aborted.")

    argv = [
        "uv",
        "run",
        "python",
        "-m",
        "app.inventory.delete.main",
        inventory_name,
    ]
    if c.cwd:
        subprocess.run(argv, check=True, cwd=c.cwd)
    else:
        subprocess.run(argv, check=True)


@task
def delete_tag(c: Context) -> None:
    """Prompt for a tag name and delete it (and all its card associations)."""

    tag_name = input("Tag name to delete: ").strip()
    if not tag_name:
        raise Exit("Tag name is required.")

    reply = input(f"Delete tag {tag_name!r} and all its card associations? Type 'yes' to confirm: ")
    if reply.strip().lower() != "yes":
        raise Exit("Aborted.")

    argv = ["uv", "run", "python", "-m", "app.tag.delete_main", tag_name]
    if c.cwd:
        subprocess.run(argv, check=True, cwd=c.cwd)
    else:
        subprocess.run(argv, check=True)


ns = Collection("delete")
ns.add_task(delete_inventory, name="inventory")
ns.add_task(delete_tag, name="tag")
