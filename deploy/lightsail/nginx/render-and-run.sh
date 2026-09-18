#!/bin/sh
# Renders nginx.conf.template with envsubst (bundled in the nginx image already, for its own
# templating feature — reused directly here instead of that feature since we need a stream {}
# block too, which lives outside the http-context conf.d/ layout that feature targets).
set -eu

envsubst '${MCP_DOMAIN} ${KEYCLOAK_DOMAIN} ${KEYCLOAK_ADMIN_DOMAIN} ${FLOWER_DOMAIN} ${ADMIN_ALLOWED_IP} ${POSTGRES_PUBLIC_PORT}' \
    < /etc/nginx/templates/nginx.conf.template > /etc/nginx/nginx.conf

exec nginx -g 'daemon off;'
