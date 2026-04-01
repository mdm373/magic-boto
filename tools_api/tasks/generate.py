"""Generate tasks — invoke wrappers that delegate to app entrypoints."""

from __future__ import annotations

import subprocess

from invoke import Collection, Context, Exit, task


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
ns.add_task(tag_audit, default=True)
