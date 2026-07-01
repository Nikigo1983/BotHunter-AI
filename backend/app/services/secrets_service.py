from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.runtime_settings import RuntimeSettingsService


@dataclass(slots=True)
class SecretStatus:
    name: str
    masked_value: str
    configured: bool
    last_verified_at: datetime | None
    status: str


def mask_secret(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return "—"
    if len(cleaned) <= 4:
        return "*" * len(cleaned)
    return f"{'*' * 12}{cleaned[-4:]}"


class SecretsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._env = get_settings()

    async def list_secrets(self) -> list[SecretStatus]:
        runtime = await RuntimeSettingsService(self._session).get_effective_settings()
        now = datetime.now(UTC)
        return [
            SecretStatus(
                name="Telegram Bot Token",
                masked_value=mask_secret(runtime.bot_token),
                configured=bool(runtime.bot_token.strip()),
                last_verified_at=now if runtime.bot_token.strip() else None,
                status="ok" if runtime.bot_token.strip() else "missing",
            ),
            SecretStatus(
                name="OpenRouter API Key",
                masked_value=mask_secret(runtime.openrouter_api_key),
                configured=bool(runtime.openrouter_api_key.strip()),
                last_verified_at=now if runtime.openrouter_api_key.strip() else None,
                status="ok" if runtime.openrouter_api_key.strip() else "missing",
            ),
            SecretStatus(
                name="OpenAI API Key",
                masked_value=mask_secret(runtime.openai_api_key),
                configured=bool(runtime.openai_api_key.strip()),
                last_verified_at=now if runtime.openai_api_key.strip() else None,
                status="ok" if runtime.openai_api_key.strip() else "missing",
            ),
            SecretStatus(
                name="Redis",
                masked_value=mask_secret(f"{self._env.redis_host}:{self._env.redis_port}"),
                configured=True,
                last_verified_at=now,
                status="ok",
            ),
            SecretStatus(
                name="Database",
                masked_value=mask_secret(f"{self._env.postgres_user}@{self._env.postgres_host}"),
                configured=True,
                last_verified_at=now,
                status="ok",
            ),
        ]
