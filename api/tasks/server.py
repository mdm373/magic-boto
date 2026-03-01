"""Server tasks."""

from invoke import Context, task


@task(default=True)
def start(c: Context) -> None:
    """Run the API server (uvicorn)."""
    c.run("uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
