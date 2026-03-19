"""Postgres environment derivation for Invoke tasks.

Centralizes PG* env building from POSTGRES_* defaults, so tasks stay consistent.
"""

from __future__ import annotations

import os


def pg_env() -> dict[str, str]:
    """Return environment for Postgres CLIs based on POSTGRES_* (or PG* if already set)."""
    env = dict(os.environ)

    def _get(name: str, default: str) -> str:
        val = env.get(name)
        return val if val else default

    # Mirror the repo's POSTGRES_* defaults used elsewhere.
    env["PGHOST"] = _get("PGHOST", _get("POSTGRES_HOST", "localhost"))
    env["PGPORT"] = _get("PGPORT", _get("POSTGRES_PORT", "5432"))
    env["PGUSER"] = _get("PGUSER", _get("POSTGRES_USER", "magicboto"))
    env["PGDATABASE"] = _get("PGDATABASE", _get("POSTGRES_DB", "magicboto"))
    env["PGPASSWORD"] = _get("PGPASSWORD", _get("POSTGRES_PASSWORD", "magicboto"))
    return env
