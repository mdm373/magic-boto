"""Generate tasks — invoke wrappers that delegate to app entrypoints."""

from __future__ import annotations

import subprocess

from invoke import Collection, Context, Exit, task


def _prompt_yn(prompt: str) -> bool:
    reply = input(f"{prompt} [y/N] ").strip().lower()
    return reply == "y"


@task
def tags(
    c: Context,
    tag: str = "",
    include_unsure: bool | None = None,
    include_excluded: bool | None = None,
) -> None:
    """Run an unattended Claude-driven tag sweep against the local database.

    Any omitted argument will be prompted for interactively.
    Model and page limit are read from settings.
    """
    if not tag.strip():
        tag = input("Tag name to sweep: ").strip()
    if not tag:
        raise Exit("Tag name is required.")

    if include_unsure is None:
        include_unsure = _prompt_yn(f"Tag uncertain cards with '{tag}_unsure'?")

    if include_excluded is None:
        include_excluded = _prompt_yn(f"Tag non-qualifying cards with '{tag}_excluded'?")

    argv = ["uv", "run", "python", "-m", "app.tag.sweep.main", tag]
    if include_unsure:
        argv += ["--include-unsure"]
    if include_excluded:
        argv += ["--include-excluded"]

    if c.cwd:
        subprocess.run(argv, check=True, cwd=c.cwd)
    else:
        subprocess.run(argv, check=True)


@task
def tag_audit(
    c: Context,
    tag: str = "",
    tagged_sample: int = 20,
    excluded_sample: int = 20,
    unsure_sample: int = 10,
) -> None:
    """Audit tag sweep results by sampling tagged/excluded/unsure cards with Claude Opus.

    Samples random cards from each bucket, sends them to Claude Opus for analysis,
    and opens the resulting feedback report automatically.
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
        "app.tag.audit.main",
        tag,
        "--tagged-sample",
        str(tagged_sample),
        "--excluded-sample",
        str(excluded_sample),
        "--unsure-sample",
        str(unsure_sample),
    ]

    if c.cwd:
        subprocess.run(argv, check=True, cwd=c.cwd)
    else:
        subprocess.run(argv, check=True)


ns = Collection("generate")
ns.add_task(tags, default=True)
ns.add_task(tag_audit)
