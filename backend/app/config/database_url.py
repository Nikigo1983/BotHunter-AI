from __future__ import annotations

from urllib.parse import unquote, urlparse


def normalize_async_database_url(url: str, *, use_pooler: bool = False) -> str:
    normalized = url.strip()
    if normalized.startswith("postgres://"):
        normalized = "postgresql+asyncpg://" + normalized[len("postgres://") :]
    elif normalized.startswith("postgresql://") and "+asyncpg" not in normalized:
        normalized = "postgresql+asyncpg://" + normalized[len("postgresql://") :]

    if not use_pooler:
        return normalized

    parsed = urlparse(normalized.replace("postgresql+asyncpg://", "postgresql://", 1))
    if not parsed.hostname:
        return normalized

    pooler_host = apply_neon_pooler_host(parsed.hostname)
    if pooler_host == parsed.hostname:
        return normalized

    auth = ""
    if parsed.username:
        auth = parsed.username
        if parsed.password:
            auth = f"{auth}:{parsed.password}"
        auth = f"{auth}@"

    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or ""
    query = f"?{parsed.query}" if parsed.query else ""
    return f"postgresql+asyncpg://{auth}{pooler_host}{port}{path}{query}"


def host_requires_postgres_ssl(host: str) -> bool:
    lowered = host.lower()
    return "neon.tech" in lowered


def apply_neon_pooler_host(host: str) -> str:
    if "-pooler." in host or not host.endswith(".neon.tech"):
        return host
    first_dot = host.find(".")
    if first_dot == -1:
        return host
    return f"{host[:first_dot]}-pooler{host[first_dot:]}"


def parse_database_url(url: str, *, use_pooler: bool = False) -> dict[str, str | int]:
    normalized = normalize_async_database_url(url, use_pooler=use_pooler)
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
