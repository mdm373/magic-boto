"""Lint task: ruff and mypy."""

import os

from invoke import Context, task


@task(default=True)
def all(c: Context) -> None:
    """Run ruff check, format, and mypy."""
    c.run("uv run ruff check . --fix && uv run ruff format .")
    c.run(f"uv run mypy app tasks --no-incremental --cache-dir={os.devnull}")
