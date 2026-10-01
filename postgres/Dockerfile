# Pins the Postgres version in one place. Both docker-compose.yml (local stack) and
# postgres/fly.toml (Fly.io) build from this image, so bumping the version here updates both.
FROM postgres:16-alpine

# No-ops unless AUTHELIA_DB_NAME is set; creates the Authelia database in this same instance
# (local and Fly both set it — see docker-compose.yml and postgres/fly.toml). See init-db.sh.
COPY init-db.sh /docker-entrypoint-initdb.d/init-db.sh

# Memory tuning for the 256MB Fly Machine this runs on (~207MB usable). Stock postgres:16
# defaults assume a far larger host: shared_buffers=128MB alone is 62% of this box before a
# single backend starts, leaving it permanently about one query from death. On 2026-10-01 a
# backend was OOM-killed (signal 9) mid-ingest, taking the whole cluster into crash recovery and
# surfacing as a 502 through the MCP server.
#
# `-c` flags are the official image's documented config mechanism — the entrypoint execs whatever
# follows `postgres`. There is deliberately no env-var indirection: the image maps no env var to
# a GUC (it understands only POSTGRES_USER/PASSWORD/DB, PGDATA, POSTGRES_INITDB_ARGS,
# POSTGRES_INITDB_WALDIR, POSTGRES_HOST_AUTH_METHOD), so an env-driven version would mean a
# wrapper script that reduces to these same flags. Values are sized for the smaller of the two
# targets; the local Compose stack simply runs conservatively.
#
# shared_buffers and max_connections are `postmaster` context — changing them needs a restart,
# not just a reload. max_connections=50 clears the ~30 that mcp + worker can open at SQLAlchemy's
# default pool (5 + 10 overflow per engine, two process groups), with room for migrations.
CMD ["postgres", \
     "-c", "shared_buffers=32MB", \
     "-c", "effective_cache_size=96MB", \
     "-c", "work_mem=2MB", \
     "-c", "maintenance_work_mem=32MB", \
     "-c", "max_connections=50"]
