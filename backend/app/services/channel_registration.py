import re
from typing import Final

from aiogram import Bot
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Chat, ChatMemberAdministrator, User as TelegramUserProfile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.channel_connection_error import ChannelConnectionError
from app.models.telegram_bot import TelegramBot
from app.models.telegram_channel import TelegramChannel
from app.models.user import User
from app.repositories.deps import (
    get_channel_connection_error_repository,
    get_telegram_bot_repository,
    get_telegram_channel_repository,
    get_user_repository,
)
from app.services.channel_registration_types import (
    ChannelRegistrationFailure,
    ChannelRegistrationSuccess,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

CHANNEL_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^-?\d+$")

REQUIRED_PERMISSIONS: Final[tuple[tuple[str, str], ...]] = (
    ("can_invite_users", "Invite Users"),
    ("can_manage_chat", "Manage Join Requests"),
)


class ChannelRegistrationService:
    def __init__(
        self,
        session: AsyncSession,
        bot: Bot,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._bot = bot
        self._settings = settings or get_settings()
        self._user_repo = get_user_repository(session)
        self._bot_repo = get_telegram_bot_repository(session)
        self._channel_repo = get_telegram_channel_repository(session)
        self._error_repo = get_channel_connection_error_repository(session)

    @staticmethod
    def parse_channel_id(raw_value: str) -> int | None:
        cleaned = raw_value.strip()
        if not cleaned or not CHANNEL_ID_PATTERN.fullmatch(cleaned):
            return None
        return int(cleaned)

    async def register_channel(
        self,
        *,
        requester: TelegramUserProfile,
        channel_id_raw: str,
    ) -> ChannelRegistrationSuccess | ChannelRegistrationFailure:
        parsed_channel_id = self.parse_channel_id(channel_id_raw)
        if parsed_channel_id is None:
            return await self._fail(
                telegram_id=requester.id,
                channel_id=None,
                reason="Некорректный ID канала. Отправьте числовой ID, например: -1001234567890",
            )

        chat, chat_error = await self._fetch_chat(parsed_channel_id)
        if chat_error or chat is None:
            return await self._fail(
                telegram_id=requester.id,
                channel_id=parsed_channel_id,
                reason=chat_error or "Канал не найден.",
            )

        if chat.type not in {ChatType.CHANNEL, ChatType.SUPERGROUP}:
            return await self._fail(
                telegram_id=requester.id,
                channel_id=parsed_channel_id,
                reason="Указанный чат не является Telegram-каналом или супергруппой.",
            )

        permission_error = await self._verify_bot_permissions(parsed_channel_id)
        if permission_error:
            return await self._fail(
                telegram_id=requester.id,
                channel_id=parsed_channel_id,
                reason=permission_error,
            )

        existing_channel = await self._channel_repo.get_by_telegram_chat_id(parsed_channel_id)
        if existing_channel is not None:
            return await self._fail(
                telegram_id=requester.id,
                channel_id=parsed_channel_id,
                reason="Этот канал уже подключён к BotHunter AI.",
            )

        owner = await self._get_or_create_owner(requester)
        platform_bot = await self._get_or_create_platform_bot(owner)

        invite_link = await self._resolve_invite_link(chat)
        channel = await self._channel_repo.create(
            TelegramChannel(
                owner_id=owner.id,
                bot_id=platform_bot.id,
                telegram_chat_id=parsed_channel_id,
                title=chat.title or "Без названия",
                invite_link=invite_link,
                is_active=True,
            )
        )

        logger.info(
            "Channel connected | telegram_chat_id=%s | owner_telegram_id=%s",
            parsed_channel_id,
            requester.id,
        )

        return ChannelRegistrationSuccess(
            channel=channel,
            title=channel.title,
            telegram_chat_id=parsed_channel_id,
        )

    async def _fetch_chat(self, chat_id: int) -> tuple[Chat | None, str | None]:
        try:
            chat = await self._bot.get_chat(chat_id)
            return chat, None
        except TelegramForbiddenError:
            return None, (
                "Бот не имеет доступа к каналу. "
                "Добавьте BotHunter AI в администраторы канала."
            )
        except TelegramBadRequest:
            return None, "Канал не найден. Проверьте ID и попробуйте снова."

    async def _verify_bot_permissions(self, chat_id: int) -> str | None:
        bot_profile = await self._bot.get_me()

        try:
            member = await self._bot.get_chat_member(chat_id, bot_profile.id)
        except (TelegramBadRequest, TelegramForbiddenError):
            return (
                "Не удалось проверить права бота. "
                "Убедитесь, что бот добавлен в администраторы канала."
            )

        if member.status == ChatMemberStatus.CREATOR:
            return None

        if member.status != ChatMemberStatus.ADMINISTRATOR:
            return "Бот не является администратором канала."

        if not isinstance(member, ChatMemberAdministrator):
            return "Не удалось определить права администратора бота."

        missing_permissions = [
            label
            for attr, label in REQUIRED_PERMISSIONS
            if not getattr(member, attr, False)
        ]
        if missing_permissions:
            permissions_text = ", ".join(missing_permissions)
            return f"У бота отсутствуют права: {permissions_text}."

        return None

    async def _resolve_invite_link(self, chat: Chat) -> str | None:
        if chat.invite_link:
            return chat.invite_link
        if chat.username:
            return f"https://t.me/{chat.username}"
        return None

    async def _get_or_create_owner(self, requester: TelegramUserProfile) -> User:
        owner = await self._user_repo.get_by_telegram_id(requester.id)
        if owner is not None:
            return owner

        full_name = requester.full_name or requester.username or f"User {requester.id}"
        return await self._user_repo.create(
            User(
                email=f"tg_{requester.id}@bothunter.local",
                password_hash="telegram-linked",
                full_name=full_name,
                telegram_id=requester.id,
            )
        )

    async def _get_or_create_platform_bot(self, owner: User) -> TelegramBot:
        bot_profile = await self._bot.get_me()
        username = bot_profile.username or f"bot_{bot_profile.id}"

        platform_bot = await self._bot_repo.get_by_bot_username(username)
        if platform_bot is not None:
            return platform_bot

        return await self._bot_repo.create(
            TelegramBot(
                owner_id=owner.id,
                bot_token=self._settings.bot_token,
                bot_username=username,
            )
        )

    async def _fail(
        self,
        *,
        telegram_id: int,
        channel_id: int | None,
        reason: str,
    ) -> ChannelRegistrationFailure:
        await self._error_repo.create(
            ChannelConnectionError(
                telegram_id=telegram_id,
                channel_id=channel_id,
                reason=reason,
            )
        )
        logger.warning(
            "Channel connection failed | telegram_id=%s | channel_id=%s | reason=%s",
            telegram_id,
            channel_id,
            reason,
        )
        return ChannelRegistrationFailure(reason=reason, telegram_chat_id=channel_id)
