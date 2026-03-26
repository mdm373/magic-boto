"""Fetch task wrappers. Heavy logic lives under ``app.fetch``."""

from invoke import Collection, Context, task


@task(default=True)
def all_sets(c: Context) -> None:
    """Run MTGJSON fetch/ingest pipeline."""
    c.run("uv run python -m app.fetch.main")


ns = Collection("fetch")
ns.add_task(all_sets, name="all_sets")
