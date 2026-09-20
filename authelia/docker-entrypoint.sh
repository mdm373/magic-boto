#!/bin/sh
# Resolves the {{ VAR }} placeholders in configuration.yml.template/users_database.yml.template
set -eu

render() {
    awk '{
        while (match($0, /\{\{[ \t]*[A-Za-z_][A-Za-z0-9_]*[ \t]*\}\}/)) {
            name = substr($0, RSTART + 2, RLENGTH - 4)
            gsub(/^[ \t]+|[ \t]+$/, "", name)
            val = ENVIRON[name]
            $0 = substr($0, 1, RSTART - 1) val substr($0, RSTART + RLENGTH)
        }
        print
    }' "$1"
}

export AUTHELIA_CLAUDE_CONNECTOR_CLIENT_SECRET_HASH="$(cat /secrets/claude_connector_client_secret_hash)"
export AUTHELIA_ADMIN_PASSWORD_HASH="$(cat /secrets/admin_password_hash)"

render /config/configuration.yml.template > /config/configuration.yml
render /config/users_database.yml.template > /config/users_database.yml

unset AUTHELIA_CLAUDE_CONNECTOR_CLIENT_SECRET_HASH AUTHELIA_ADMIN_PASSWORD_HASH

exec /app/entrypoint.sh "$@"
