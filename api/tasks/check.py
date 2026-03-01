"""Check task: run ruff (check + format check)."""

from invoke import Context, task


@task(default=True)
def run(c: Context) -> None:
    """Run ruff check and format check."""
    c.run("uv run ruff check . && uv run ruff format --check .")
