#!/bin/sh
set -e

if [ -z "$AUTHELIA_DB_NAME" ]; then
    exit 0
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE "$AUTHELIA_DB_NAME";
EOSQL
