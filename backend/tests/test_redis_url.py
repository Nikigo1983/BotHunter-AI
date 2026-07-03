from app.config.settings import Settings, get_settings


def test_redis_url_uses_redis_url_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "REDIS_URL",
        "rediss://default:secret@loving-ferret-128792.upstash.io:6379",
    )
    get_settings.cache_clear()
    settings = Settings()
    assert settings.redis_url == "rediss://default:secret@loving-ferret-128792.upstash.io:6379"


def test_redis_url_falls_back_to_host_port(monkeypatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_URL", raising=False)
    get_settings.cache_clear()
    settings = Settings()
    assert settings.redis_url == "redis://localhost:6379/0"
