"""Generate tasks: OpenAPI schema and DB schema dump. Run from tools_api/."""

from pathlib import Path

from invoke import Context, task

from .pg_env import pg_env


def _write_openapi_schema(c: Context) -> None:
    """Write FastAPI OpenAPI schema to tools_api/debug/openapi.json."""
    script = (
        "from pathlib import Path; "
        "from app.main import app; "
        "p = Path('debug'); p.mkdir(exist_ok=True); "
        "p.joinpath('openapi.json').write_text(__import__('json').dumps(app.openapi(), indent=2)); "
        "print('Wrote debug/openapi.json')"
    )
    c.run(f'uv run python -c "{script}"')


@task
def openapi_schema(c: Context) -> None:
    """Write FastAPI OpenAPI schema to tools_api/debug/openapi.json."""
    _write_openapi_schema(c)


@task
def db_schema(c: Context) -> None:
    """Update tools_api/debug/schema.sql from the live DB (pg_dump -s)."""
    out_dir = Path("debug")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "schema.sql"

    env = pg_env()
    print(f"Dumping schema to: {out_path}")
    c.run(f'pg_dump -s -f "{out_path}"', env=env)


@task(default=True, pre=[openapi_schema, db_schema])
def all(c: Context) -> None:
    """Generate OpenAPI schema (debug/openapi.json) and DB schema (debug/schema.sql)."""
    pass
