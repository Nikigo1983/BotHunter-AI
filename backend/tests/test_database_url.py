from app.config.database_url import (
    apply_neon_pooler_host,
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


def test_apply_neon_pooler_host() -> None:
    host = "ep-cool-darkness-123456.us-east-2.aws.neon.tech"
    assert apply_neon_pooler_host(host) == "ep-cool-darkness-123456-pooler.us-east-2.aws.neon.tech"


def test_settings_postgres_vars_with_pooler(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    settings = Settings(
        postgres_host="ep-cool-darkness-123456.us-east-2.aws.neon.tech",
        postgres_port=5432,
        postgres_user="neondb_owner",
        postgres_password="secret",
        postgres_db="neondb",
        database_use_pooler=True,
    )
    assert "-pooler.us-east-2.aws.neon.tech" in settings.database_url
