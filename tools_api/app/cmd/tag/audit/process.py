"""Tag audit process — fetch batch results, persist report, save to file."""

from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger

from app.db import cli_session_scope
from app.log import configure_cli_logging
from app.services import create_tag_audit_processing_service


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process a completed tag audit batch.")
    parser.add_argument("audit_id", help="Tag audit UUID.")
    return parser.parse_args()


async def _run(audit_id: str) -> None:
    proc = create_tag_audit_processing_service()
    async with cli_session_scope() as session:
        await proc.run(session, audit_id)


def main() -> None:
    configure_cli_logging()
    args = _parse_args()
    try:
        asyncio.run(_run(args.audit_id))
    except ValueError as e:
        logger.error("{}", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
