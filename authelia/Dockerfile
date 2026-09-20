# Pins the Authelia version in one place; both docker-compose.yml (local stack, build: ./authelia)
# and authelia/fly.toml build this same image so local and Fly run identically.
FROM authelia/authelia:4.38

# Baked in as *templates* (see configuration.yml/users_database.yml's own header comments) —
# docker-entrypoint.sh resolves the __TOKEN__ placeholders into the actual paths Authelia reads
# (/config/configuration.yml, /config/users_database.yml) at container start, since their values
# are only known at runtime (differ per environment, or come from secret files).
COPY configuration.yml /config/configuration.yml.template
COPY users_database.yml /config/users_database.yml.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
