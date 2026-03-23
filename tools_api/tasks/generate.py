"""Generate tasks: OpenAPI schema and DB schema dump. Run from tools_api/."""

from pathlib import Path

from invoke import Context, task

from .pg_env import pg_env


@task(default=True)
def db_schema(c: Context) -> None:
    """Update tools_api/debug/schema.sql from the live DB (pg_dump -s)."""
    out_dir = Path("debug")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "schema.sql"

    env = pg_env()
    print(f"Dumping schema to: {out_path}")
    c.run(f'pg_dump -s -f "{out_path}"', env=env)
