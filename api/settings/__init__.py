"""Application settings from environment and .env (Pydantic)."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env at repo root (parent of api/)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    """App configuration from env vars and .env at repo root."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres
    postgres_host: str = "localhost"
    postgres_port: str = "5432"
    postgres_user: str = "magicboto"
    postgres_password: str = "magicboto"
    postgres_db: str = "magicboto"

    # LM Studio (OpenAI-compatible). From Docker use host.docker.internal.
    lm_studio_base_url: str = "http://localhost:1234"
    lm_studio_timeout: float = 120.0

    # OpenAI-compatible base URL (this API). From UI in Docker: http://api:8000/openapi/v1.
    openapi_base_url: str = "http://localhost:8000/openapi/v1"

    @field_validator("lm_studio_base_url", "openapi_base_url", mode="before")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/") if isinstance(v, str) else v


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached app settings (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
