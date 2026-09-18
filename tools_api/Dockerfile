# Tools API for magic-boto. After changing pyproject.toml: docker compose build --no-cache tools_api
FROM python:3.11-slim

WORKDIR /app

# postgresql-client: `uv run invoke migrate` always chains into `export.db-schema`
# (tasks/migrate.py), which shells out to `pg_dump -s` to keep tools_api/debug/schema.sql in
# sync — needed in every container built from this image, not just ones that serve HTTP traffic.
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock* ./
RUN pip install uv && uv sync --no-dev --no-install-project

COPY . .
RUN uv sync --no-dev

EXPOSE 8000 8765
CMD ["uv", "run", "uvicorn", "app.cmd.serve_http:app", "--host", "0.0.0.0", "--port", "8000"]
