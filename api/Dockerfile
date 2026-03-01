# API server for magic-boto (agent + tools). See docs/PROJECT-PLAN.md.
FROM python:3.11-slim

WORKDIR /app

# Install uv and sync dependencies (no dev). After changing pyproject.toml, rebuild:
#   docker compose build --no-cache api
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --no-dev --no-install-project

# Copy app and install project.
COPY . .
RUN uv sync --no-dev

# Run uvicorn. Env (POSTGRES_*, etc.) provided by docker-compose.
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
