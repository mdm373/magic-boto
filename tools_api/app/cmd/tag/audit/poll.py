"""Tag audit poll — check and update the Anthropic batch status for an audit."""

from __future__ import annotations

import argparse
import sys
import uuid
from collections.abc import Sequence

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository import TagAuditRepo
from app.services import create_batch_poller


class _AuditPollProvider:
    def __init__(self) -> None:
        self._audit_repo = TagAuditRepo()

    def populate_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.description = "Poll Anthropic batch status for a tag audit."
        parser.add_argument("audit_id", help="Tag audit UUID.")

    async def fetch_batch_ids(
        self, session: AsyncSession, args: argparse.Namespace
    ) -> Sequence[uuid.UUID]:
        audit = await self._audit_repo.get_audit(session, uuid.UUID(args.audit_id))
        if audit is None:
            logger.error("Audit {} not found.", args.audit_id)
            sys.exit(1)
        if audit.batch is None:
            logger.error("Audit {} has no batch — run kickoff first.", args.audit_id)
            sys.exit(1)
        return [audit.batch.id]


def main() -> None:
    create_batch_poller(_AuditPollProvider()).run()


if __name__ == "__main__":
    main()
