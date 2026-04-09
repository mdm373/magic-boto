"""Sweep enqueue — submit Anthropic batches for a tag (default) or Celery-only for existing work."""

from __future__ import annotations

import argparse
import asyncio
import uuid

from app.db import sqlalchemy_resources_lifespan
from app.log import configure_cli_logging
from app.services.tag_sweep_initializer import create_tag_sweep_initializer
from app.worker import enqueue_process_sweep_run


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
        help="With --existing: do not tag uncertain cards with {tag}_unsure during process.",
    )
    parser.add_argument(
        "--no-include-excluded",
        action="store_true",
        default=False,
        help="With --existing: skip {tag}_excluded during process.",
    )
    parser.add_argument(
        "--audit-after",
        action="store_true",
        default=False,
        help="After sweep process, run audit enqueue and its Celery pipeline.",
    )
    parser.add_argument("--audit-tagged-sample", type=int, default=20, metavar="N")
    parser.add_argument("--audit-excluded-sample", type=int, default=40, metavar="N")
    parser.add_argument("--audit-unsure-sample", type=int, default=10, metavar="N")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    configure_cli_logging()
    if args.existing:
        enqueue_process_sweep_run(
            args.tag,
            include_unsure=not args.no_include_unsure,
            include_excluded=not args.no_include_excluded,
            audit_after=args.audit_after,
            audit_tagged_sample=args.audit_tagged_sample,
            audit_excluded_sample=args.audit_excluded_sample,
            audit_unsure_sample=args.audit_unsure_sample,
        )
        return

    async def _kickoff() -> uuid.UUID | None:
        async with sqlalchemy_resources_lifespan() as r:
            async with r.session_scope() as session:
                result = await create_tag_sweep_initializer().kickoff(
                    session,
                    args.tag,
                    args.limit,
                    args.reenqueue_failed,
                )
            if result.batch_submitted:
                enqueue_process_sweep_run(
                    args.tag,
                    include_unsure=True,
                    include_excluded=True,
                    audit_after=args.audit_after,
                    audit_tagged_sample=args.audit_tagged_sample,
                    audit_excluded_sample=args.audit_excluded_sample,
                    audit_unsure_sample=args.audit_unsure_sample,
                )
            return result.run_id

    run_id = asyncio.run(_kickoff())
    if run_id is not None:
        print(run_id, flush=True)


if __name__ == "__main__":
    main()
