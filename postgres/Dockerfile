# Pins the Postgres version in one place. Both docker-compose.yml (local stack) and
# postgres/fly.toml (Fly.io) build from this image, so bumping the version here updates both.
FROM postgres:16-alpine

# No-ops unless AUTHELIA_DB_NAME is set; creates the Authelia database in this same instance
# (local and Fly both set it — see docker-compose.yml and postgres/fly.toml). See init-db.sh.
COPY init-db.sh /docker-entrypoint-initdb.d/init-db.sh
