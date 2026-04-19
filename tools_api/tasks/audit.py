"""Audit tasks — invoke wrappers for ``app.cmd.tag.audit.*``."""

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
    audit_id: str = "",
    tagged_sample: int = 20,
    excluded_sample: int = 70,
    unsure_sample: int = 10,
) -> None:
    """Run ``python -m app.cmd.tag.audit.enqueue`` (new batch or ``--audit-id`` Celery-only)."""
    tag = tag.strip()
    audit_id = audit_id.strip()
    if not audit_id and not tag:
        tag = input("Tag name (or press Enter to use audit ID only): ").strip()
        if not tag:
            audit_id = input("Audit ID: ").strip()
    if audit_id:
        argv = [
            "uv",
            "run",
            "python",
            "-m",
            "app.cmd.tag.audit.enqueue",
            "--audit-id",
            audit_id,
        ]
    elif tag:
        argv = [
            "uv",
            "run",
            "python",
            "-m",
            "app.cmd.tag.audit.enqueue",
            tag,
            "--tagged-sample",
            str(tagged_sample),
            "--excluded-sample",
            str(excluded_sample),
            "--unsure-sample",
            str(unsure_sample),
        ]
    else:
        raise Exit("Tag name or audit ID is required.")

    _run_subprocess(c, argv)


@task
def process(c: Context, audit_id: str = "") -> None:
    """Run ``python -m app.cmd.tag.audit.process``."""
    if not audit_id.strip():
        audit_id = input("Audit ID: ").strip()
    if not audit_id:
        raise Exit("Audit ID is required.")

    _run_subprocess(
        c,
        ["uv", "run", "python", "-m", "app.cmd.tag.audit.process", audit_id],
    )


@task
def apply(
    c: Context,
    tag: str = "",
    delete_tagged: bool = False,
    delete_side_tags: bool = False,
) -> None:
    """Run ``python -m app.cmd.tag.audit.apply``."""
    if not tag.strip():
        tag = input("Tag name: ").strip()
    if not tag:
        raise Exit("Tag name is required.")

    argv = ["uv", "run", "python", "-m", "app.cmd.tag.audit.apply", tag]
    if delete_tagged:
        argv.append("--delete-tagged")
    if delete_side_tags:
        argv.append("--delete-side-tags")
    _run_subprocess(c, argv)


ns = Collection("audit")
ns.add_task(enqueue, default=True)
ns.add_task(process)
ns.add_task(apply)
