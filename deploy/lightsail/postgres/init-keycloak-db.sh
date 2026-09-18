#!/bin/sh
# Prod-only: mounted into the shared postgres container's /docker-entrypoint-initdb.d/ (see
# docker-compose.prod.yml) so Keycloak gets its own database inside the same Postgres instance as
# the app, instead of a second Postgres container — the biggest single memory win available on a
# small instance short of shrinking the JVM itself. Like every script in that directory, this only
# runs once, against a brand-new (empty) tools_db_postgres_data volume; it does nothing on a
# volume that's already initialized.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE "${KEYCLOAK_DB_NAME:-keycloak}";
EOSQL
