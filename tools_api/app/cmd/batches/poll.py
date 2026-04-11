"""CLI: enqueue Celery pipeline poll for batch UUIDs, then the chosen process task when terminal."""

from __future__ import annotations

import argparse
import re
import sys
import uuid

from loguru import logger

from app.log import configure_cli_logging
from app.worker.pipeline_task_names import PipelineTaskName, is_after_poll_target
from app.worker.poll_pipeline import enqueue_poll_pipeline

_AFTER_POLL_ALIASES: dict[str, PipelineTaskName] = {
    "process_sweep_run": PipelineTaskName.PROCESS_SWEEP_RUN,
    "sweep": PipelineTaskName.PROCESS_SWEEP_RUN,
    "process_tag_audit": PipelineTaskName.PROCESS_TAG_AUDIT,
    "audit": PipelineTaskName.PROCESS_TAG_AUDIT,
}


def _parse_batch_ids(raw: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[\s,]+", raw.strip()) if p.strip()]
    if not parts:
        raise ValueError("At least one batch id is required.")
    out: list[str] = []
    for p in parts:
        try:
            out.append(str(uuid.UUID(p)))
        except ValueError as e:
            raise ValueError(f"Invalid batch UUID: {p!r}") from e
    return out


def _parse_after_poll(raw: str) -> PipelineTaskName:
    key = raw.strip()
    if not key:
        raise ValueError("--after-poll is required.")
    if key in _AFTER_POLL_ALIASES:
        return _AFTER_POLL_ALIASES[key]
    try:
        name = PipelineTaskName(key)
    except ValueError as e:
        allowed = ", ".join(
            sorted(
                {
                    *_AFTER_POLL_ALIASES,
                    str(PipelineTaskName.PROCESS_SWEEP_RUN),
                    str(PipelineTaskName.PROCESS_TAG_AUDIT),
                }
            )
        )
        raise ValueError(f"Invalid --after-poll {raw!r}. Use one of: {allowed}") from e
    if not is_after_poll_target(name):
        raise ValueError(f"Invalid --after-poll task for pipeline poll: {raw!r}")
    return name


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Enqueue Celery poll_pipeline for the given batch UUIDs. "
            "When all batches are terminal, the worker enqueues the post-poll task "
            "(process_sweep_run or process_tag_audit)."
        )
    )
    parser.add_argument(
        "--batch-ids",
        required=True,
        metavar="UUIDS",
        help="Comma- or whitespace-separated batch UUIDs (magic_boto.batches.id).",
    )
    parser.add_argument(
        "--after-poll",
        required=True,
        metavar="TASK",
        help=(
            "Celery task to run after all batches are terminal: "
            "process_sweep_run, process_tag_audit, sweep, audit, "
            "or full name e.g. app.worker.tasks.process_sweep_run."
        ),
    )
    parser.add_argument(
        "--countdown",
        type=int,
        default=None,
        metavar="SEC",
        help="Optional initial countdown (seconds) before first poll iteration.",
    )
    args = parser.parse_args()
    configure_cli_logging()
    try:
        batch_ids = _parse_batch_ids(args.batch_ids)
        target = _parse_after_poll(args.after_poll)
    except ValueError as e:
        logger.error("{}", e)
        sys.exit(1)

    enqueue_poll_pipeline(target, batch_ids, countdown=args.countdown)
    logger.info(
        "Enqueued poll_pipeline for {} batch id(s) → after terminal: {}",
        len(batch_ids),
        target,
    )


if __name__ == "__main__":
    main()
