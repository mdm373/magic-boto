"""Sweep tasks — invoke wrappers for the batch sweep pipeline."""

from __future__ import annotations

import subprocess
import webbrowser

from invoke import Collection, Context, Exit, task

from ._import import _read_multiline

_BATCHES_URL = "https://platform.claude.com/workspaces/default/batches"


def _prompt_yn(prompt: str) -> bool:
    """Prompt the operator for a yes/no answer. Returns True for 'y'."""
    answer = input(f"{prompt} [y/N] ").strip().lower()
    return answer in {"y", "yes"}


@task
def kickoff(
    c: Context,
    tag: str = "",
    limit: int = 0,
    reenqueue_failed: bool = False,
) -> None:
    """Submit Anthropic batch requests for cards pending a tag sweep.

    Resumes an existing open run for the tag, or creates a new one.
    Use --limit N to submit N cards and exit; re-run kickoff to resume.
    Use --reenqueue-failed to re-submit oracle IDs from failed batches in the open run.
    """
    if not tag.strip():
        tag = input("Tag name to sweep: ").strip()
    if not tag:
        raise Exit("Tag name is required.")

    argv = ["uv", "run", "python", "-m", "app.tag.kickoff.main", tag]
    if limit > 0:
        argv += ["--limit", str(limit)]
    if reenqueue_failed:
        argv += ["--reenqueue-failed"]

    if c.cwd:
        subprocess.run(argv, check=True, cwd=c.cwd)
    else:
        subprocess.run(argv, check=True)
    webbrowser.open(_BATCHES_URL)


@task
def poll(
    c: Context,
    run_id: str = "",
    wait: bool = False,
) -> None:
    """Check and update Anthropic batch statuses for a sweep run.

    With --wait, loops every 30s until all batches reach a terminal state.
    """
    if not run_id.strip():
        run_id = input("Run ID: ").strip()
    if not run_id:
        raise Exit("Run ID is required.")

    argv = ["uv", "run", "python", "-m", "app.tag.poll.main", run_id]
    if wait:
        argv += ["--wait"]

    if c.cwd:
        subprocess.run(argv, check=True, cwd=c.cwd)
    else:
        subprocess.run(argv, check=True)


@task
def process(
    c: Context,
    run_id: str = "",
    include_unsure: bool | None = None,
    include_excluded: bool | None = None,
) -> None:
    """Apply tags from completed batch results for a sweep run.

    All batches must be in a terminal state before running (use sweep.poll --wait).
    """
    if not run_id.strip():
        run_id = input("Run ID: ").strip()
    if not run_id:
        raise Exit("Run ID is required.")

    if include_unsure is None:
        include_unsure = _prompt_yn("Tag uncertain cards with {tag}_unsure?")
    if include_excluded is None:
        include_excluded = _prompt_yn("Tag non-qualifying cards with {tag}_excluded?")

    argv = ["uv", "run", "python", "-m", "app.tag.process.main", run_id]
    if include_unsure:
        argv += ["--include-unsure"]
    if include_excluded:
        argv += ["--include-excluded"]

    if c.cwd:
        subprocess.run(argv, check=True, cwd=c.cwd)
    else:
        subprocess.run(argv, check=True)


@task
def run(
    c: Context,
    tag: str = "",
    limit: int = 0,
) -> None:
    """Full sweep orchestration: create or select a tag, kick off batches, poll, then process.

    Prompts to create a new tag or use an existing one, then runs the full pipeline end-to-end.
    """
    # --- Tag selection ---
    use_existing = _prompt_yn("Use an existing tag?")
    if use_existing:
        if not tag.strip():
            tag = input("Tag name to sweep: ").strip()
        if not tag:
            raise Exit("Tag name is required.")
    else:
        tag = input("Tag name: ").strip()
        if not tag:
            raise Exit("Tag name is required.")
        types_raw = input("Sweep include types: ").strip()
        supertypes_raw = input("Sweep include supertypes: ").strip()
        description = _read_multiline("Tag description (two blank lines to finish):")
        if not description:
            raise Exit("Tag description is required.")
        create_argv = ["uv", "run", "python", "-m", "app.tag.create.main", tag, description]
        if types_raw:
            create_argv += [f"--types={types_raw}"]
        if supertypes_raw:
            create_argv += [f"--supertypes={supertypes_raw}"]
        _run_subprocess(c, create_argv)

    # --- Limit ---
    if limit == 0:
        raw = input("Card limit per kickoff run (blank for no limit): ").strip()
        if raw.isdigit():
            limit = int(raw)

    include_unsure = _prompt_yn("Tag uncertain cards with {tag}_unsure?")
    include_excluded = _prompt_yn("Tag non-qualifying cards with {tag}_excluded?")

    # --- Kickoff ---
    kickoff_argv = ["uv", "run", "python", "-m", "app.tag.kickoff.main", tag]
    if limit > 0:
        kickoff_argv += ["--limit", str(limit)]
    result = _run_subprocess(c, kickoff_argv, capture_stdout=True)
    run_id = result.stdout.strip()
    if not run_id:
        raise Exit("Kickoff did not return a run ID.")

    # --- Poll ---
    _run_subprocess(c, ["uv", "run", "python", "-m", "app.tag.poll.main", run_id, "--wait"])

    # --- Process ---
    process(c, run_id=run_id, include_unsure=include_unsure, include_excluded=include_excluded)


@task
def reset(c: Context, tag: str = "") -> None:
    """Show or delete the open sweep run for a tag.

    Without --delete, prints current run and batch state.
    With --delete, deletes the open run (cascades to batches) so kickoff starts fresh.
    """
    if not tag.strip():
        tag = input("Tag name: ").strip()
    if not tag:
        raise Exit("Tag name is required.")

    # Show current state first.
    result = _run_subprocess(
        c,
        ["uv", "run", "python", "-m", "app.tag.reset.main", tag],
        capture_stdout=True,
    )
    run_id = result.stdout.strip()
    if not run_id:
        return

    if not _prompt_yn(f"Delete run {run_id} and all its batches? Kickoff will start fresh."):
        return

    _run_subprocess(c, ["uv", "run", "python", "-m", "app.tag.reset.main", tag, "--delete"])


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
    return subprocess.run(argv, **kwargs)  # type: ignore[call-overload]


ns = Collection("sweep")
ns.add_task(kickoff)
ns.add_task(poll)
ns.add_task(process)
ns.add_task(run, default=True)
ns.add_task(reset)
