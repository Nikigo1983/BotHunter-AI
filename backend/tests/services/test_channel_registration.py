from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.types import Chat, ChatMemberAdministrator, User as TelegramUserProfile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel_connection_error import ChannelConnectionError
from app.repositories.deps import (
    get_channel_connection_error_repository,
    get_telegram_channel_repository,
)
from app.services.channel_registration import ChannelRegistrationService
from app.services.channel_registration_types import (
    ChannelRegistrationFailure,
    ChannelRegistrationSuccess,
)


@pytest.fixture
def telegram_user() -> TelegramUserProfile:
    return TelegramUserProfile(
        id=700001,
        is_bot=False,
        first_name="Owner",
        username="owner_user",
    )


@pytest.fixture
def mock_bot() -> AsyncMock:
    bot = AsyncMock()
    bot.get_me.return_value = MagicMock(id=8389397180, username="bothunter_AI_bot")
    return bot


def make_admin_member(*, invite: bool = True, manage_chat: bool = True) -> ChatMemberAdministrator:
    return ChatMemberAdministrator(
        status=ChatMemberStatus.ADMINISTRATOR,
        user=TelegramUserProfile(
            id=8389397180,
            is_bot=True,
            first_name="BotHunter",
            username="bothunter_AI_bot",
        ),
        can_be_edited=False,
        is_anonymous=False,
        can_manage_chat=manage_chat,
        can_delete_messages=False,
        can_manage_video_chats=False,
        can_restrict_members=False,
        can_promote_members=False,
        can_change_info=False,
        can_invite_users=invite,
        can_post_messages=False,
        can_edit_messages=False,
        can_pin_messages=False,
        can_manage_topics=False,
        can_post_stories=False,
        can_edit_stories=False,
        can_delete_stories=False,
    )


@pytest.mark.asyncio
async def test_parse_channel_id() -> None:
    assert ChannelRegistrationService.parse_channel_id("-1001234567890") == -1001234567890
    assert ChannelRegistrationService.parse_channel_id("  -100999  ") == -100999
    assert ChannelRegistrationService.parse_channel_id("abc") is None
    assert ChannelRegistrationService.parse_channel_id("") is None


@pytest.mark.asyncio
async def test_register_channel_success(
    session: AsyncSession,
    mock_bot: AsyncMock,
    telegram_user: TelegramUserProfile,
) -> None:
    channel_id = -1005550001
    mock_bot.get_chat.return_value = Chat(
        id=channel_id,
        type=ChatType.CHANNEL,
        title="Test Channel",
        username="testchannel",
    )
    mock_bot.get_chat_member.return_value = make_admin_member()

    service = ChannelRegistrationService(session, mock_bot)
    result = await service.register_channel(
        requester=telegram_user,
        channel_id_raw=str(channel_id),
    )

    assert isinstance(result, ChannelRegistrationSuccess)
    assert result.title == "Test Channel"
    assert result.telegram_chat_id == channel_id

    channel_repo = get_telegram_channel_repository(session)
    stored = await channel_repo.get_by_telegram_chat_id(channel_id)
    assert stored is not None
    assert stored.is_active is True


@pytest.mark.asyncio
async def test_register_channel_invalid_id_saves_error(
    session: AsyncSession,
    mock_bot: AsyncMock,
    telegram_user: TelegramUserProfile,
) -> None:
    service = ChannelRegistrationService(session, mock_bot)
    result = await service.register_channel(
        requester=telegram_user,
        channel_id_raw="not-a-channel-id",
    )

    assert isinstance(result, ChannelRegistrationFailure)
    error_repo = get_channel_connection_error_repository(session)
    errors = await error_repo.get_all(limit=10)
    assert any(
        isinstance(item, ChannelConnectionError)
        and item.telegram_id == telegram_user.id
        and item.channel_id is None
        for item in errors
    )


@pytest.mark.asyncio
async def test_register_channel_missing_permissions(
    session: AsyncSession,
    mock_bot: AsyncMock,
    telegram_user: TelegramUserProfile,
) -> None:
    channel_id = -1005550002
    mock_bot.get_chat.return_value = Chat(
        id=channel_id,
        type=ChatType.CHANNEL,
        title="Restricted Channel",
    )
    mock_bot.get_chat_member.return_value = make_admin_member(invite=False, manage_chat=False)

    service = ChannelRegistrationService(session, mock_bot)
    result = await service.register_channel(
        requester=telegram_user,
        channel_id_raw=str(channel_id),
    )

    assert isinstance(result, ChannelRegistrationFailure)
    assert "Invite Users" in result.reason
    assert "Manage Join Requests" in result.reason


@pytest.mark.asyncio
async def test_register_channel_bot_not_admin(
    session: AsyncSession,
    mock_bot: AsyncMock,
    telegram_user: TelegramUserProfile,
) -> None:
    channel_id = -1005550003
    mock_bot.get_chat.return_value = Chat(
        id=channel_id,
        type=ChatType.CHANNEL,
        title="No Admin Channel",
    )
    mock_bot.get_chat_member.return_value = MagicMock(status=ChatMemberStatus.MEMBER)

    service = ChannelRegistrationService(session, mock_bot)
    result = await service.register_channel(
        requester=telegram_user,
        channel_id_raw=str(channel_id),
    )

    assert isinstance(result, ChannelRegistrationFailure)
    assert "администратором" in result.reason.lower()


@pytest.mark.asyncio
async def test_register_channel_already_connected(
    session: AsyncSession,
    mock_bot: AsyncMock,
    telegram_user: TelegramUserProfile,
) -> None:
    channel_id = -1005550004
    mock_bot.get_chat.return_value = Chat(
        id=channel_id,
        type=ChatType.CHANNEL,
        title="Existing",
    )
    mock_bot.get_chat_member.return_value = make_admin_member()

    service = ChannelRegistrationService(session, mock_bot)
    first_result = await service.register_channel(
        requester=telegram_user,
        channel_id_raw=str(channel_id),
    )
    assert isinstance(first_result, ChannelRegistrationSuccess)

    second_result = await service.register_channel(
        requester=telegram_user,
        channel_id_raw=str(channel_id),
    )

    assert isinstance(second_result, ChannelRegistrationFailure)
    assert "уже подключён" in second_result.reason
