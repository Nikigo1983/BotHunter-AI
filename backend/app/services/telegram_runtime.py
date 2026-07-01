import uuid

from aiogram import Bot
from aiogram.utils.token import TokenValidationError, validate_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.organization import OrganizationSecretsRuntime


class TelegramRuntimeService:
    PLACEHOLDER_TOKENS = frozenset({"", "your-telegram-bot-token"})

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._secrets = OrganizationSecretsRuntime(session)

    async def resolve_token(self, organization_id: uuid.UUID | None) -> str:
        if organization_id is not None:
            org_token = await self._secrets.resolve_telegram_bot_token(organization_id)
            if org_token and self._is_valid_token(org_token):
                return org_token.strip()
        global_token = self._settings.bot_token.strip()
        if self._is_valid_token(global_token):
            return global_token
        return ""

    async def get_bot(
        self,
        organization_id: uuid.UUID | None,
        *,
        fallback: Bot | None = None,
    ) -> Bot:
        token = await self.resolve_token(organization_id)
        if not token:
            if fallback is not None:
                return fallback
            raise ValueError("Telegram bot token is not configured")
        if fallback is not None and token == self._settings.bot_token.strip():
            return fallback
        return Bot(token=token)

    def _is_valid_token(self, token: str) -> bool:
        cleaned = token.strip()
        if cleaned in self.PLACEHOLDER_TOKENS:
            return False
        try:
            validate_token(cleaned)
        except TokenValidationError:
            return False
        return True
