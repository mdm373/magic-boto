"""Application settings from environment variables. Set env before starting the process."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tools API configuration (Postgres only)."""

    model_config = SettingsConfigDict(extra="ignore")

    postgres_host: str = "localhost"
    postgres_port: str = "5432"
    postgres_user: str = "magicboto"
    postgres_password: str = "magicboto"
    postgres_db: str = "magicboto"
    mtgjson_base_url: str = Field(default="https://mtgjson.com")
    mtgjson_cache_dir: str = Field(default=".mtg_json")
    mtgjson_cache_max_age_days: float = Field(
        default=1.0,
        description="TTL for SetList.json cache only; per-set JSON files use existence-only cache.",
    )
    mtgjson_fetch_user_agent: str = Field(default="magic-boto-tools-api/0.1 (MTGJSON fetch task)")
    mtgjson_fetch_sleep_seconds: float = Field(default=1.0)
    mtgjson_insert_batch_size: int = Field(default=500)

    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key — required for the generate.tags sweep task only.",
    )

    tag_sweep_model: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Anthropic model ID used by the tag sweep task.",
    )
    tag_sweep_limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Cards per page for the tag sweep task.",
    )
    tag_sweep_max_tokens: int = Field(
        default=2048,
        ge=256,
        description="Max tokens for each Claude call in the tag sweep task.",
    )
    debug_output_dir: str = Field(
        default="debug",
        description="Directory for debug output files (Claude logs, unsure-card logs, etc.).",
    )

    inventory_import_max_unknown_scryfall_ids: int = Field(
        default=100,
        ge=0,
        description=(
            "CSV inventory import: abort (after rollback) if more than this many distinct "
            "Scryfall ids are missing from the catalog. Missing ids are always logged first."
        ),
    )

    @field_validator("mtgjson_base_url")
    @classmethod
    def _strip_mtgjson_base_url(cls, v: str) -> str:
        return v.rstrip("/")


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached settings (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
