"""CLI: delete an inventory by name."""

from __future__ import annotations

import asyncio
import sys

from app.db import get_async_session_factory
from app.inventory.names import canonical_inventory_name
from app.services import create_inventory_service

service = create_inventory_service()


def _parse_args() -> str:
    args = sys.argv[1:]
    if len(args) != 1:
        raise ValueError("Usage: python -m app.inventory.delete.main <inventory_name>")
    return args[0]


async def _run(inventory_name: str) -> None:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        inv = await service.get_inventory_by_name(session, inventory_name)
        if inv is None:
            canon = canonical_inventory_name(inventory_name)
            print(f"No inventory named {canon!r}.")
            sys.exit(1)
        name = inv.name
        deleted = await service.delete_inventory(session, inv.id)
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
