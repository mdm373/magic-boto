"""Sweep enqueue — submit Anthropic batches for a tag (default) or Celery-only for existing work."""

from __future__ import annotations

import argparse
import asyncio

from app.db import cli_session_scope
from app.log import configure_cli_logging
from app.services.tag_sweep_initializer import (
    SweepKickoffRequest,
    create_tag_sweep_initializer,
)
from app.services.tag_sweep_service import create_tag_sweep_service
from app.worker import (
    PipelineTaskName,
    enqueue_process_sweep_polling,
    enqueue_submit_batches,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Submit sweep batches for a tag and enqueue Celery (default), or enqueue Celery only."
        )
    )
    parser.add_argument("tag", help="Tag name (must exist).")
    parser.add_argument(
        "--existing",
        action="store_true",
        help="Enqueue Celery only for batches already submitted (no new Anthropic batches).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help=("Submit at most N cards; run stays open. 0 = no limit. Ignored with --existing."),
    )
    parser.add_argument(
        "--reenqueue-failed",
        action="store_true",
        default=False,
        help="Re-submit failed oracle IDs in the open run. Ignored with --existing.",
    )
    parser.add_argument(
        "--no-include-unsure",
        action="store_true",
        default=False,
        help="Default path: do not tag uncertain cards with {tag}_unsure during process.",
    )
    parser.add_argument(
        "--no-include-excluded",
        action="store_true",
        default=False,
        help="Default path: skip {tag}_excluded during process.",
    )
    parser.add_argument(
        "--audit-after",
        action="store_true",
        default=False,
        help="Default path: after sweep process, run audit enqueue and its Celery pipeline.",
    )
    parser.add_argument("--audit-tagged-sample", type=int, default=20, metavar="N")
    parser.add_argument("--audit-excluded-sample", type=int, default=40, metavar="N")
    parser.add_argument("--audit-unsure-sample", type=int, default=10, metavar="N")
    return parser


async def _existing_poll_batch_ids(tag_name: str) -> list[str]:
    sweep_service = create_tag_sweep_service()
    async with cli_session_scope() as session:
        return await sweep_service.get_open_sweep_batch_ids(session, tag_name)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    configure_cli_logging()
    if args.existing:
        batch_ids = asyncio.run(_existing_poll_batch_ids(args.tag))
        enqueue_process_sweep_polling(batch_ids)
        return

    async def body() -> list[str]:
        async with cli_session_scope() as session:
            init = create_tag_sweep_initializer()
            sweep_service = create_tag_sweep_service()
            request = SweepKickoffRequest(
                tag_name=args.tag,
                limit=args.limit,
                reenqueue_failed=args.reenqueue_failed,
                include_unsure=not args.no_include_unsure,
                include_excluded=not args.no_include_excluded,
                audit_after=args.audit_after,
                audit_tagged_sample=args.audit_tagged_sample,
                audit_excluded_sample=args.audit_excluded_sample,
                audit_unsure_sample=args.audit_unsure_sample,
            )
            sweep = await init.init_sweep(session, request)
            batch_ids = await sweep_service.get_pending_batch_ids_for_sweep(session, sweep)
            if not batch_ids:
                raise ValueError(f"No pending batches for sweep {sweep.id}.")
            return list(batch_ids)

    batch_ids = asyncio.run(body())
    enqueue_submit_batches(batch_ids, PipelineTaskName.PROCESS_SWEEP_RUN)


if __name__ == "__main__":
    main()
