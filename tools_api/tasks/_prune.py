"""Prune task: delete side tags and audits for a tag."""

from __future__ import annotations

import subprocess

from invoke import Collection, Context, Exit, task


@task(default=True)
def prune_tag(c: Context) -> None:
    """Delete side tags (_unsure, _excluded) and all audits for a tag."""
    tag_name = input("Tag name to prune: ").strip()
    if not tag_name:
        raise Exit("Tag name is required.")

    reply = input(f"Delete side tags and audits for {tag_name!r}? Type 'yes' to confirm: ")
    if reply.strip().lower() != "yes":
        raise Exit("Aborted.")

    argv = ["uv", "run", "python", "-m", "app.cmd.tag.prune", tag_name]
    if c.cwd:
        subprocess.run(argv, check=True, cwd=c.cwd)
    else:
        subprocess.run(argv, check=True)


@task()
def prune_all(c: Context) -> None:
    """Prune side tags, audits, and sweep batch history for every primary tag."""
    reply = input("Prune all tags (side tags, audits, sweep batches)? Type 'yes' to confirm: ")
    if reply.strip().lower() != "yes":
        raise Exit("Aborted.")

    argv = ["uv", "run", "python", "-m", "app.cmd.tag.prune", "--all"]
    if c.cwd:
        subprocess.run(argv, check=True, cwd=c.cwd)
    else:
        subprocess.run(argv, check=True)


ns = Collection("prune")
ns.add_task(prune_tag, name="tag", default=True)
ns.add_task(prune_all, name="all")
