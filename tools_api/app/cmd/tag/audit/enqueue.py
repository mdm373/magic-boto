"""Audit enqueue — by default submit an Anthropic audit batch and enqueue Celery."""

from __future__ import annotations

import argparse
import asyncio
import uuid

from app.db import sqlalchemy_resources_lifespan
from app.log import configure_cli_logging
from app.services.tag_audit_initializer import create_tag_audit_initializer
from app.worker import enqueue_process_tag_audit


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Submit an audit batch for a tag and enqueue Celery (default), or enqueue Celery only."
        )
    )
    parser.add_argument(
        "tag",
        nargs="?",
        help="Tag name (sweep results must exist). Submits Anthropic batch and enqueues Celery.",
    )
    parser.add_argument(
        "--audit-id",
        metavar="UUID",
        help="Poll existing audit until ready and then process it.",
    )
    parser.add_argument("--tagged-sample", type=int, default=20, metavar="N")
    parser.add_argument("--excluded-sample", type=int, default=40, metavar="N")
    parser.add_argument("--unsure-sample", type=int, default=10, metavar="N")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if (args.tag is None) == (args.audit_id is None):
        parser.error(
            "Provide TAG (submit batch and enqueue Celery) or --audit-id UUID (Celery only)."
        )
    configure_cli_logging()
    if args.audit_id is not None:
        audit_uuid = uuid.UUID(args.audit_id)
        enqueue_process_tag_audit(str(audit_uuid))
        return

    async def _kickoff() -> uuid.UUID:
        async with sqlalchemy_resources_lifespan() as r:
            async with r.session_scope() as session:
                audit_id = await create_tag_audit_initializer().init_audit(
                    session,
                    args.tag,
                    args.tagged_sample,
                    args.excluded_sample,
                    args.unsure_sample,
                )
            enqueue_process_tag_audit(str(audit_id))
            return audit_id

    audit_id = asyncio.run(_kickoff())
    print(audit_id, flush=True)


if __name__ == "__main__":
    main()
