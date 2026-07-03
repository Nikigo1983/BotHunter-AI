from __future__ import annotations

from urllib.parse import unquote, urlparse


def normalize_async_database_url(url: str) -> str:
    normalized = url.strip()
    if normalized.startswith("postgres://"):
        return "postgresql+asyncpg://" + normalized[len("postgres://") :]
    if normalized.startswith("postgresql://") and "+asyncpg" not in normalized:
        return "postgresql+asyncpg://" + normalized[len("postgresql://") :]
    return normalized


def host_requires_postgres_ssl(host: str) -> bool:
    lowered = host.lower()
    return "neon.tech" in lowered


def parse_database_url(url: str) -> dict[str, str | int]:
    normalized = normalize_async_database_url(url)
    parsed = urlparse(normalized.replace("postgresql+asyncpg://", "postgresql://", 1))
    if not parsed.hostname:
        raise ValueError("DATABASE_URL must include a hostname")

    database = parsed.path.lstrip("/") or "postgres"
    return {
        "postgres_host": parsed.hostname,
        "postgres_port": parsed.port or 5432,
        "postgres_user": unquote(parsed.username or ""),
        "postgres_password": unquote(parsed.password or ""),
        "postgres_db": database,
    }
