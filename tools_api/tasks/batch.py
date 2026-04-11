"""Batch pipeline helpers — poll + post-poll process via Celery."""

from __future__ import annotations

import subprocess

from invoke import Collection, Context, Exit, task


def _run_subprocess(
    c: Context,
    argv: list[str],
) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, object] = {"check": True, "text": True}
    if c.cwd:
        kwargs["cwd"] = c.cwd
    return subprocess.run(argv, **kwargs)  # type: ignore[call-overload, no-any-return]


@task
def poll(
    c: Context,
    batch_ids: str = "",
    after_poll: str = "",
    countdown: int | None = None,
) -> None:
    """Enqueue Celery ``poll_pipeline`` for batch UUIDs; prompts when args omitted.

    Post-poll: ``process_sweep_run`` / ``process_tag_audit`` (aliases ``sweep`` / ``audit``).
    """
    if not batch_ids.strip():
        batch_ids = input("Comma-separated batch UUIDs: ").strip()
    if not batch_ids:
        raise Exit("At least one batch id is required.")

    if not after_poll.strip():
        print("Post-poll Celery task (runs when all batches are terminal):")
        print("  process_sweep_run  — tag sweep processor")
        print("  process_tag_audit  — tag audit processor")
        print("  (aliases: sweep, audit)")
        after_poll = input("After-poll task [process_sweep_run]: ").strip() or "process_sweep_run"

    argv = [
        "uv",
        "run",
        "python",
        "-m",
        "app.cmd.batches.poll",
        "--batch-ids",
        batch_ids,
        "--after-poll",
        after_poll,
    ]
    if countdown is not None:
        argv += ["--countdown", str(countdown)]

    _run_subprocess(c, argv)


ns = Collection("batch")
ns.add_task(poll, name="poll", default=True)
