from app.config.settings import Settings, get_settings


def test_resolve_app_port_falls_back_to_port_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_PORT", "${{PORT}}")
    monkeypatch.setenv("PORT", "8765")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.app_port == 8765


def test_resolve_app_port_ignores_empty_app_port(monkeypatch) -> None:
    monkeypatch.setenv("APP_PORT", "")
    monkeypatch.setenv("PORT", "3000")
    get_settings.cache_clear()
    settings = Settings()
    assert settings.app_port == 3000
