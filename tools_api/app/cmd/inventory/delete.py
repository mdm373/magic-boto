"""CLI: delete an inventory by name."""

from __future__ import annotations

import asyncio
import sys

from app.db import sqlalchemy_resources_lifespan
from app.repository import InventoryRepo, canonical_name

_inv_repo = InventoryRepo()


def _parse_args() -> str:
    args = sys.argv[1:]
    if len(args) != 1:
        raise ValueError("Usage: python -m app.cmd.inventory.delete <inventory_name>")
    return args[0]


async def _run(inventory_name: str) -> None:
    async with sqlalchemy_resources_lifespan() as r:
        async with r.session_scope() as session:
            inv = await _inv_repo.get_by_name(session, inventory_name)
            if inv is None:
                canon = canonical_name(inventory_name)
                print(f"No inventory named {canon!r}.")
                sys.exit(1)
            name = inv.name
            deleted = await _inv_repo.delete(session, inv.id)
        if deleted:
            print(f"Deleted inventory {name!r}.")
        else:
            print("Delete did not remove a row (unexpected).")
            sys.exit(1)


def main() -> None:
    raw = _parse_args()
    asyncio.run(_run(raw))


if __name__ == "__main__":
    main()
