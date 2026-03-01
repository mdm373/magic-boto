"""Verify task: ruff, mypy, then test."""

from invoke import Context, task

from tasks import test as test_tasks


@task(default=True)
def run(c: Context) -> None:
    """Run ruff, mypy, and pytest (full verify)."""
    c.run("uv run ruff check . && uv run ruff format --check .")
    c.run("uv run mypy app migrations tasks --no-incremental")
    test_tasks.run(c)
