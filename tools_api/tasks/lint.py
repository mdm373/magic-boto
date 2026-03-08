"""Lint task: ruff and mypy."""

from invoke import Context, task


@task(default=True)
def all(c: Context) -> None:
    """Run ruff check, format, and mypy."""
    c.run("uv run ruff check . --fix && uv run ruff format . && uv run mypy app tasks")
