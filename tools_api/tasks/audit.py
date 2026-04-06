"""Audit tasks — invoke wrappers for the batch tag audit pipeline."""

from __future__ import annotations

import subprocess

from invoke import Collection, Context, Exit, task

from .sweep import _prompt_yn


def _run_subprocess(
    c: Context,
    argv: list[str],
    capture_stdout: bool = False,
) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, object] = {"check": True, "text": True}
    if capture_stdout:
        kwargs["stdout"] = subprocess.PIPE
    if c.cwd:
        kwargs["cwd"] = c.cwd
    return subprocess.run(argv, **kwargs)  # type: ignore[call-overload, no-any-return]


@task
def kickoff(
    c: Context,
    tag: str = "",
    tagged_sample: int = 20,
    excluded_sample: int = 40,
    unsure_sample: int = 10,
) -> None:
    """Sample cards and submit an Anthropic batch for tag quality review.

    Prints the audit ID on completion — pass it to audit.poll and audit.process.
    """
    if not tag.strip():
        tag = input("Tag name to audit: ").strip()
    if not tag:
        raise Exit("Tag name is required.")

    argv = [
        "uv",
        "run",
        "python",
        "-m",
        "app.cmd.tag.audit.kickoff",
        tag,
        "--tagged-sample",
        str(tagged_sample),
        "--excluded-sample",
        str(excluded_sample),
        "--unsure-sample",
        str(unsure_sample),
    ]
    _run_subprocess(c, argv)


@task
def poll(
    c: Context,
    audit_id: str = "",
    wait: bool = False,
) -> None:
    """Check and update the Anthropic batch status for a tag audit.

    With --wait, loops every 30s until the batch reaches a terminal state.
    """
    if not audit_id.strip():
        audit_id = input("Audit ID: ").strip()
    if not audit_id:
        raise Exit("Audit ID is required.")

    argv = ["uv", "run", "python", "-m", "app.cmd.tag.audit.poll", audit_id]
    if wait:
        argv += ["--wait"]
    _run_subprocess(c, argv)


@task
def process(
    c: Context,
    audit_id: str = "",
) -> None:
    """Fetch audit batch results, save the report to DB and open the file."""
    if not audit_id.strip():
        audit_id = input("Audit ID: ").strip()
    if not audit_id:
        raise Exit("Audit ID is required.")

    _run_subprocess(c, ["uv", "run", "python", "-m", "app.cmd.tag.audit.process", audit_id])


@task
def run(
    c: Context,
    tag: str = "",
    tagged_sample: int = 20,
    excluded_sample: int = 40,
    unsure_sample: int = 10,
) -> None:
    """Full audit pipeline: kickoff → poll --wait → process."""
    if not tag.strip():
        tag = input("Tag name to audit: ").strip()
    if not tag:
        raise Exit("Tag name is required.")

    kickoff_argv = [
        "uv",
        "run",
        "python",
        "-m",
        "app.cmd.tag.audit.kickoff",
        tag,
        "--tagged-sample",
        str(tagged_sample),
        "--excluded-sample",
        str(excluded_sample),
        "--unsure-sample",
        str(unsure_sample),
    ]
    result = _run_subprocess(c, kickoff_argv, capture_stdout=True)
    audit_id = result.stdout.strip()
    if not audit_id:
        raise Exit("Kickoff did not return an audit ID.")

    _run_subprocess(c, ["uv", "run", "python", "-m", "app.cmd.tag.audit.poll", audit_id, "--wait"])
    _run_subprocess(c, ["uv", "run", "python", "-m", "app.cmd.tag.audit.process", audit_id])


@task
def apply(c: Context, tag: str = "") -> None:
    """Apply the latest audit suggestion to a tag, optionally reset tags, then kick off a new sweep."""
    if not tag.strip():
        tag = input("Tag name: ").strip()
    if not tag:
        raise Exit("Tag name is required.")

    apply_argv = ["uv", "run", "python", "-m", "app.cmd.tag.audit.apply", tag]

    if _prompt_yn("Delete all tagged/unsure/excluded cards for this tag?", default=True):
        apply_argv.append("--delete-tagged")

    if _prompt_yn("Delete the _unsure and _excluded side tags entirely?", default=True):
        apply_argv.append("--delete-side-tags")

    _run_subprocess(c, apply_argv)

    if not _prompt_yn("Kick off a new sweep for this tag?", default=True):
        return

    _run_subprocess(c, ["uv", "run", "invoke", "sweep", "--tag", tag])


ns = Collection("audit")
ns.add_task(kickoff)
ns.add_task(poll)
ns.add_task(process)
ns.add_task(apply)
ns.add_task(run, default=True)
