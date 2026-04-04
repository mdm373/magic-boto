"""Database restore task."""

from __future__ import annotations

from pathlib import Path

from invoke import Collection, Context, Exit, task

from .pg_env import pg_env

_DUMPS_DIR = Path("pg_dump")


def _pick_dump() -> Path:
    dumps = sorted(_DUMPS_DIR.glob("*.pgdump"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    if not dumps:
        raise Exit(f"No .pgdump files found in {_DUMPS_DIR}/")

    print("Recent dumps:")
    for i, p in enumerate(dumps, 1):
        print(f"  {i}) {p.name}")

    raw = input("Select [1] or enter a path: ").strip()
    if not raw or raw == "1":
        return dumps[0]
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(dumps):
            return dumps[idx]
        raise Exit(f"Invalid selection: {raw}")
    return Path(raw)


@task(default=True)
def db_restore(c: Context) -> None:
    """List recent .pgdump files and restore the selected one."""
    dump_path = _pick_dump()

    env = pg_env()
    db = env["PGDATABASE"]

    confirm = input(f"Drop and recreate '{db}', then restore from {dump_path.name}? [y/N] ")
    confirm = confirm.strip().lower()
    if confirm != "y":
        raise Exit("Aborted.")

    print(f"Dropping database '{db}'...")
    c.run(f"dropdb --if-exists {db}", env=env)
    print(f"Creating database '{db}'...")
    c.run(f"createdb {db}", env=env)
    print(f"Restoring from: {dump_path}")
    c.run(f'pg_restore -Fc -d "{db}" "{dump_path}"', env=env)
    print("Done.")


ns = Collection("restore")
ns.add_task(db_restore, name="db", default=True)
