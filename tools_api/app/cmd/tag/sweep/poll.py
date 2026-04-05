"""Batch sweep poll — check and update Anthropic batch statuses for a sweep run."""

from __future__ import annotations

import argparse
import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.tag_repo import TagRepo
from app.repository.tag_sweep_repo import TagSweepRepo
from app.services import create_batch_poller


class _SweepPollProvider:
    def __init__(self) -> None:
        self._repo = TagSweepRepo()
        self._tag_repo = TagRepo()

    def populate_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.description = "Poll Anthropic batch status for a sweep run."
        parser.add_argument("tag", help="Tag name.")

    async def fetch_batch_ids(
        self, session: AsyncSession, args: argparse.Namespace
    ) -> Sequence[uuid.UUID]:
        tag = await self._tag_repo.require_tag_model(session, args.tag)
        sweep = await self._repo.get_open_sweep(session, tag.id)
        if sweep is None:
            raise ValueError(f"No open sweep found for tag '{args.tag}'.")
        sweep_batches = await self._repo.get_batches(session, sweep.id)
        return [sb.batch_id for sb in sweep_batches]


def main() -> None:
    create_batch_poller(_SweepPollProvider()).run()


if __name__ == "__main__":
    main()
