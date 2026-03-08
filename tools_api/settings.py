"""Settings from env. Populate env before run (e.g. scripts/load-env.ps1)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tools API configuration (Postgres only)."""

    model_config = SettingsConfigDict(extra="ignore")

    postgres_host: str = "localhost"
    postgres_port: str = "5432"
    postgres_user: str = "magicboto"
    postgres_password: str = "magicboto"
    postgres_db: str = "magicboto"


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached settings (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
