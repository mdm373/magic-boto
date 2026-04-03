"""Tag audit process — fetch batch results, persist report, save to file."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger
from sqlalchemy import select

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.models.magic_boto_tag import MagicBotoTagModel
from app.models.sweep_status import BatchStatus
from app.services import create_batch_service, create_tag_audit_service
from app.tag.batch.client import create_batch_client
from settings import get_settings

_audit_service = create_tag_audit_service()
_batch_service = create_batch_service()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process a completed tag audit batch.")
    parser.add_argument("audit_id", help="Tag audit UUID.")
    return parser.parse_args()


async def _run(audit_id_str: str) -> None:
    audit_id = uuid.UUID(audit_id_str)
    settings = get_settings()
    session_factory = get_async_session_factory()

    async with session_factory() as session:
        audit = await _audit_service.get_audit(session, audit_id)
        if audit is None:
            logger.error("Audit {} not found.", audit_id)
            sys.exit(1)
        if audit.batch is None:
            logger.error("Audit {} has no batch — run kickoff first.", audit_id)
            sys.exit(1)
        if audit.batch.status != BatchStatus.ENDED:
            logger.error(
                "Batch is not in ENDED state (current: {}). Run audit.poll --wait first.",
                audit.batch.status,
            )
            sys.exit(1)
        if audit.report is not None:
            logger.warning("Audit {} already has a report — re-processing.", audit_id)

        anthropic_batch_id = audit.batch.anthropic_batch_id

    batch_client = create_batch_client()
    results = batch_client.get_results(anthropic_batch_id)

    report: str | None = None
    for result in results:
        if result.result.type == "succeeded":
            text_blocks = [b for b in result.result.message.content if b.type == "text"]
            if text_blocks:
                report = text_blocks[0].text.strip()
        else:
            logger.error(
                "Audit batch request failed with type '{}'. Cannot process.",
                result.result.type,
            )
            sys.exit(1)

    if report is None:
        logger.error("No text content in audit batch response.")
        sys.exit(1)

    async with session_factory() as session:
        audit = await _audit_service.get_audit(session, audit_id)
        if audit is None or audit.batch is None:
            logger.error("Audit {} disappeared during processing.", audit_id)
            sys.exit(1)
        audit.report = report
        _batch_service.mark_batch_processed(audit.batch)
        tag_row = await session.scalar(
            select(MagicBotoTagModel).where(MagicBotoTagModel.id == audit.tag_id)
        )
        if tag_row is None:
            logger.error("Tag {} not found for audit {}.", audit.tag_id, audit_id)
            sys.exit(1)
        tag_name = tag_row.name
        await session.commit()

    debug_dir = Path(settings.debug_output_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    output_path = debug_dir / f"{timestamp}_{tag_name}_audit.md"
    output_path.write_text(report, encoding="utf-8")
    logger.info("Audit report saved to {}.", output_path)
    os.startfile(str(output_path))


def main() -> None:
    configure_cli_logging()
    args = _parse_args()
    asyncio.run(_run(args.audit_id))


if __name__ == "__main__":
    main()
