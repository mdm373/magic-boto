"""Settings from env. Populate env before run (e.g. scripts/load-env.ps1)."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Agent API configuration: OpenAI proxy and tools_api base URL."""

    model_config = SettingsConfigDict(extra="ignore")

    openai_proxy_base_url: str = "http://localhost:1234"
    openai_proxy_timeout: float = 120.0
    tools_api_base_url: str = "http://localhost:8000"
    tools_api_timeout: float = 30.0
    max_tool_rounds: int = 10

    @field_validator("openai_proxy_base_url", "tools_api_base_url", mode="before")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/") if isinstance(v, str) else v


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached settings (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
