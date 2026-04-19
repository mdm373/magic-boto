"""Sweep tasks — invoke wrappers for ``app.cmd.tag.sweep.*``."""

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
def enqueue(
    c: Context,
    tag: str = "",
    existing: bool = False,
    limit: int | None = None,
    reenqueue_failed: bool = False,
    no_include_unsure: bool = False,
    no_include_excluded: bool = False,
    audit_after: bool = False,
    audit_tagged_sample: int = 20,
    audit_excluded_sample: int = 70,
    audit_unsure_sample: int = 10,
) -> None:
    """Run ``python -m app.cmd.tag.sweep.enqueue``.

    When not ``--existing``, prompts for a card limit if ``--limit`` is omitted (blank = no limit).
    """
    if not tag.strip():
        tag = input("Tag name: ").strip()
    if not tag:
        raise Exit("Tag name is required.")

    if limit is None:
        if not existing:
            raw = input("Card limit per enqueue run (blank for no limit): ").strip()
            limit = int(raw) if raw.isdigit() else 0
        else:
            limit = 0

    argv = ["uv", "run", "python", "-m", "app.cmd.tag.sweep.enqueue", tag]
    if existing:
        argv.append("--existing")
    if limit > 0:
        argv += ["--limit", str(limit)]
    if reenqueue_failed:
        argv.append("--reenqueue-failed")
    if no_include_unsure:
        argv.append("--no-include-unsure")
    if no_include_excluded:
        argv.append("--no-include-excluded")
    if audit_after:
        argv.append("--audit-after")
    argv += [
        "--audit-tagged-sample",
        str(audit_tagged_sample),
        "--audit-excluded-sample",
        str(audit_excluded_sample),
        "--audit-unsure-sample",
        str(audit_unsure_sample),
    ]
    _run_subprocess(c, argv)


@task
def process(
    c: Context,
    tag: str = "",
    include_unsure: bool = False,
    include_excluded: bool = False,
) -> None:
    """Run ``python -m app.cmd.tag.sweep.process``."""
    if not tag.strip():
        tag = input("Tag name: ").strip()
    if not tag:
        raise Exit("Tag name is required.")

    argv = ["uv", "run", "python", "-m", "app.cmd.tag.sweep.process", tag]
    if include_unsure:
        argv.append("--include-unsure")
    if include_excluded:
        argv.append("--include-excluded")
    _run_subprocess(c, argv)


@task
def reset(
    c: Context,
    tag: str = "",
) -> None:
    """Run ``python -m app.cmd.tag.sweep.reset`` (full clean reset)."""
    if not tag.strip():
        tag = input("Tag name: ").strip()
    if not tag:
        raise Exit("Tag name is required.")

    argv = ["uv", "run", "python", "-m", "app.cmd.tag.sweep.reset", tag]
    _run_subprocess(c, argv)


ns = Collection("sweep")
ns.add_task(enqueue, default=True)
ns.add_task(process)
ns.add_task(reset)
