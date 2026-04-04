"""Batch sweep poll — check and update Anthropic batch statuses for a sweep run."""

from __future__ import annotations

import argparse
import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.tag_sweep_repo import TagSweepRepo
from app.services import create_batch_poller


class _SweepPollProvider:
    def __init__(self) -> None:
        self._repo = TagSweepRepo()

    def populate_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.description = "Poll Anthropic batch status for a sweep run."
        parser.add_argument("sweep_id", help="Sweep run UUID.")

    async def fetch_batch_ids(
        self, session: AsyncSession, args: argparse.Namespace
    ) -> Sequence[uuid.UUID]:
        sweep_batches = await self._repo.get_batches(session, uuid.UUID(args.sweep_id))
        return [sb.batch_id for sb in sweep_batches]


def main() -> None:
    create_batch_poller(_SweepPollProvider()).run()


if __name__ == "__main__":
    main()
