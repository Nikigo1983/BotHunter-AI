from app.config.database_url import (
    host_requires_postgres_ssl,
    normalize_async_database_url,
    parse_database_url,
)
from app.config.settings import Settings, get_settings


def test_normalize_async_database_url() -> None:
    assert (
        normalize_async_database_url("postgres://user:pass@host/db")
        == "postgresql+asyncpg://user:pass@host/db"
    )


def test_parse_database_url_neon() -> None:
    parsed = parse_database_url(
        "postgresql://neondb_owner:secret@ep-example-pooler.eu-central-1.aws.neon.tech/neondb"
    )
    assert parsed["postgres_host"] == "ep-example-pooler.eu-central-1.aws.neon.tech"
    assert parsed["postgres_db"] == "neondb"
    assert parsed["postgres_user"] == "neondb_owner"
    assert parsed["postgres_password"] == "secret"


def test_settings_use_database_url_and_neon_ssl(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://neondb_owner:secret@ep-example-pooler.eu-central-1.aws.neon.tech/neondb",
    )
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    get_settings.cache_clear()
    settings = Settings()
    assert settings.postgres_host == "ep-example-pooler.eu-central-1.aws.neon.tech"
    assert settings.requires_postgres_ssl is True
    assert settings.database_url.startswith("postgresql+asyncpg://")
