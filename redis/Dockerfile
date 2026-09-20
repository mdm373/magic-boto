# Pins the Redis version in one place. Both docker-compose.yml (local stack, image directly) and
# redis/fly.toml (Fly.io) end up on the same major version.
FROM redis:7-alpine

# Persist to the mounted volume (see redis/fly.toml) with AOF enabled — without --dir pointing at
# /data, Redis writes its dump/AOF files into the container's ephemeral filesystem and loses them
# on every restart.
CMD ["redis-server", "--dir", "/data", "--appendonly", "yes"]
