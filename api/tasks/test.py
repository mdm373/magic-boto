"""Test task: run pytest."""

from invoke import Context, task


@task(default=True)
def run(c: Context) -> None:
    """Run pytest."""
    c.run("uv run pytest tests -v")
