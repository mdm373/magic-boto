"""CLI: print inventory rows as ``count name (SET) collector_number`` lines."""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.db import get_async_session_factory
from app.inventory.names import canonical_inventory_name
from app.models import MagicBotoCardModel, MagicBotoInventoryCardModel
from app.services import create_inventory_service

service = create_inventory_service()


def _parse_args() -> str:
    args = sys.argv[1:]
    if len(args) != 1:
        raise ValueError("Usage: python -m app.inventory.export.main <inventory_name>")
    return args[0]


def _format_line(
    count: int,
    name: str,
    set_code: str,
    collector_number: str | None,
) -> str:
    code = set_code.upper()
    num = (collector_number or "").strip() or "?"
    return f"{count} {name} ({code}) {num}"


async def _run(inventory_name: str) -> None:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        inv = await service.get_inventory_by_name(session, inventory_name)
        if inv is None:
            canon = canonical_inventory_name(inventory_name)
            print(f"No inventory named {canon!r}.", file=sys.stderr)
            sys.exit(1)

        stmt = (
            select(
                MagicBotoInventoryCardModel.count,
                MagicBotoCardModel.name,
                MagicBotoCardModel.set_code,
                MagicBotoCardModel.collector_number,
            )
            .join(
                MagicBotoCardModel,
                MagicBotoInventoryCardModel.card_id == MagicBotoCardModel.card_id,
            )
            .where(MagicBotoInventoryCardModel.inventory_id == inv.id)
            .order_by(
                MagicBotoCardModel.name.asc(),
                MagicBotoCardModel.set_code.asc(),
                MagicBotoCardModel.collector_number.asc().nulls_last(),
            )
        )
        result = await session.execute(stmt)
        rows = result.all()

    for qty, card_name, set_code, collector_number in rows:
        line = _format_line(qty, card_name, set_code, collector_number)
        print(line)


def main() -> None:
    raw = _parse_args()
    asyncio.run(_run(raw))


if __name__ == "__main__":
    main()
