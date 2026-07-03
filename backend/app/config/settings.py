import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.database_url import (
    host_requires_postgres_ssl,
    normalize_async_database_url,
    parse_database_url,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "BotHunter AI"
    app_env: str = "development"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    api_v1_prefix: str = "/api/v1"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "bothunter"
    postgres_password: str = "bothunter"
    postgres_db: str = "bothunter"
    postgres_ssl: bool = False
    database_url_override: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    bot_token: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_timeout: float = 30.0

    ai_provider: str = "mock"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-4.1"
    ai_timeout: float = 30.0
    ai_max_retries: int = 2

    decision_approve_below: int = 30
    decision_reject_from: int = 70
    telegram_no_phone_max_age_days: int = 45
    telegram_linked_phone_min_age_days: int = 120

    dashboard_session_secret: str = "change-me-in-production"
    dashboard_session_max_age_hours: int = 24
    dashboard_cookie_secure: bool = False
    dashboard_admin_email: str = "admin@bothunter.local"
    dashboard_admin_password: str = "admin"
    dashboard_https_enabled: bool = False
    monthly_budget_usd: float = 100.0

    @model_validator(mode="before")
    @classmethod
    def resolve_app_port(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        def parse_port(value: Any) -> int | None:
            if value is None or value == "":
                return None
            try:
                port = int(value)
            except (TypeError, ValueError):
                return None
            return port if 0 < port < 65536 else None

        port = parse_port(os.getenv("PORT"))
        if port is None:
            port = parse_port(data.get("app_port"))
        if port is not None:
            data["app_port"] = port
        return data

    @model_validator(mode="before")
    @classmethod
    def resolve_database_from_url(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        raw_url = data.get("database_url_override") or os.getenv("DATABASE_URL")
        if not raw_url:
            return data

        data["database_url_override"] = raw_url
        try:
            parsed = parse_database_url(raw_url)
        except ValueError:
            return data

        data.update(parsed)
        return data

    @property
    def requires_postgres_ssl(self) -> bool:
        if self.postgres_ssl:
            return True
        return host_requires_postgres_ssl(self.postgres_host)

    @computed_field
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return normalize_async_database_url(self.database_url_override)
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
