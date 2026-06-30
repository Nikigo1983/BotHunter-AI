from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, User as TelegramProfile

from app.bot.handlers.connect import (
    CONNECT_INSTRUCTIONS,
    FAILURE_TEMPLATE,
    SUCCESS_TEMPLATE,
    handle_connect,
    handle_telegram_channel_chat_id,
    is_telegram_channel_chat_id,
)
from app.bot.states.connect import ConnectChannelStates
from app.bot.states.debug_chatid import DebugChatIdStates
from app.repositories.deps import get_telegram_channel_repository
from app.services.channel_registration_types import (
    ChannelRegistrationFailure,
    ChannelRegistrationSuccess,
)
from tests.services.test_channel_registration import make_admin_member


def make_fsm_context(*, bot_id: int = 8389397180, user_id: int = 700001) -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=bot_id, chat_id=user_id, user_id=user_id),
    )


def make_message(
    *,
    text: str,
    user_id: int = 700001,
    username: str = "owner_user",
) -> MagicMock:
    message = MagicMock()
    message.text = text
    message.from_user = TelegramProfile(
        id=user_id,
        is_bot=False,
        first_name="Owner",
        username=username,
    )
    message.answer = AsyncMock()
    return message


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("-1004286145697", True),
        ("  -1004286145697  ", True),
        ("-1001234567890", True),
        ("-100", False),
        ("1004286145697", False),
        ("-123456", False),
        ("abc", False),
        ("Chat ID\n\n-1004286145697", False),
    ],
)
def test_is_telegram_channel_chat_id(text: str, expected: bool) -> None:
    assert is_telegram_channel_chat_id(text) is expected


@pytest.mark.asyncio
async def test_connect_command_sets_state_and_sends_instructions() -> None:
    message = make_message(text="/connect")
    state = make_fsm_context()

    await handle_connect(message, state)

    assert await state.get_state() == ConnectChannelStates.waiting_for_channel_id.state
    message.answer.assert_awaited_once_with(CONNECT_INSTRUCTIONS)


@pytest.mark.asyncio
async def test_register_channel_via_connect_fsm() -> None:
    message = make_message(text="-1004286145697")
    state = make_fsm_context()
    await state.set_state(ConnectChannelStates.waiting_for_channel_id)
    bot = AsyncMock()

    success = ChannelRegistrationSuccess(
        channel=MagicMock(),
        title="Test Channel",
        telegram_chat_id=-1004286145697,
    )

    with patch("app.bot.handlers.connect.async_session_factory") as session_factory:
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = session

        with patch("app.bot.handlers.connect.ChannelRegistrationService") as service_cls:
            service = AsyncMock()
            service.register_channel = AsyncMock(return_value=success)
            service_cls.return_value = service

            await handle_telegram_channel_chat_id(message, state, bot)

    assert await state.get_state() is None
    message.answer.assert_awaited_once()
    assert "✅ Канал успешно подключён" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_register_channel_without_connect() -> None:
    message = make_message(text="-1004286145697")
    state = make_fsm_context()
    bot = AsyncMock()

    success = ChannelRegistrationSuccess(
        channel=MagicMock(),
        title="Direct Channel",
        telegram_chat_id=-1004286145697,
    )

    with patch("app.bot.handlers.connect.async_session_factory") as session_factory:
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = session

        with patch("app.bot.handlers.connect.ChannelRegistrationService") as service_cls:
            service = AsyncMock()
            service.register_channel = AsyncMock(return_value=success)
            service_cls.return_value = service

            await handle_telegram_channel_chat_id(message, state, bot)

    service.register_channel.assert_awaited_once()
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_register_channel_after_restart_simulation() -> None:
    message = make_message(text="-1004286145697")
    state = make_fsm_context()
    assert await state.get_state() is None
    bot = AsyncMock()

    success = ChannelRegistrationSuccess(
        channel=MagicMock(),
        title="Restart Channel",
        telegram_chat_id=-1004286145697,
    )

    with patch("app.bot.handlers.connect.async_session_factory") as session_factory:
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = session

        with patch("app.bot.handlers.connect.ChannelRegistrationService") as service_cls:
            service = AsyncMock()
            service.register_channel = AsyncMock(return_value=success)
            service_cls.return_value = service

            await handle_telegram_channel_chat_id(message, state, bot)

    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_channel_after_fsm_loss() -> None:
    message = make_message(text="-1004286145697")
    state = make_fsm_context()
    await state.set_state(ConnectChannelStates.waiting_for_channel_id)
    await state.clear()
    bot = AsyncMock()

    success = ChannelRegistrationSuccess(
        channel=MagicMock(),
        title="Recovered Channel",
        telegram_chat_id=-1004286145697,
    )

    with patch("app.bot.handlers.connect.async_session_factory") as session_factory:
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = session

        with patch("app.bot.handlers.connect.ChannelRegistrationService") as service_cls:
            service = AsyncMock()
            service.register_channel = AsyncMock(return_value=success)
            service_cls.return_value = service

            await handle_telegram_channel_chat_id(message, state, bot)

    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_channel_after_debug_chatid_state() -> None:
    message = make_message(text="-1004286145697")
    state = make_fsm_context()
    await state.set_state(DebugChatIdStates.waiting_for_forward)
    bot = AsyncMock()

    success = ChannelRegistrationSuccess(
        channel=MagicMock(),
        title="Debug Override Channel",
        telegram_chat_id=-1004286145697,
    )

    with patch("app.bot.handlers.connect.async_session_factory") as session_factory:
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = session

        with patch("app.bot.handlers.connect.ChannelRegistrationService") as service_cls:
            service = AsyncMock()
            service.register_channel = AsyncMock(return_value=success)
            service_cls.return_value = service

            await handle_telegram_channel_chat_id(message, state, bot)

    assert await state.get_state() is None
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_channel_permission_error() -> None:
    message = make_message(text="-1004286145697")
    state = make_fsm_context()
    bot = AsyncMock()

    failure = ChannelRegistrationFailure(
        reason="У бота отсутствуют права: Invite Users, Manage Join Requests.",
        telegram_chat_id=-1004286145697,
    )

    with patch("app.bot.handlers.connect.async_session_factory") as session_factory:
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = session

        with patch("app.bot.handlers.connect.ChannelRegistrationService") as service_cls:
            service = AsyncMock()
            service.register_channel = AsyncMock(return_value=failure)
            service_cls.return_value = service

            await handle_telegram_channel_chat_id(message, state, bot)

    message.answer.assert_awaited_once_with(FAILURE_TEMPLATE.format(reason=failure.reason))


@pytest.mark.asyncio
async def test_non_channel_id_message_is_not_matched_by_filter() -> None:
    assert is_telegram_channel_chat_id("123456") is False
    assert is_telegram_channel_chat_id("hello") is False


@pytest.mark.asyncio
async def test_register_channel_persists_in_database(session) -> None:
    channel_id = int(f"-100{uuid.uuid4().int % 10_000_000_000:010d}")
    user_id = 700_000 + uuid.uuid4().int % 100_000
    bot = AsyncMock()
    bot.get_me.return_value = MagicMock(id=8389397180, username="bothunter_AI_bot")
    bot.get_chat.return_value = Chat(
        id=channel_id,
        type=ChatType.CHANNEL,
        title="Persisted Channel",
        username="persistedchannel",
    )
    bot.get_chat_member.return_value = make_admin_member()

    message = make_message(text=str(channel_id), user_id=user_id)
    state = make_fsm_context(user_id=user_id)

    with patch("app.bot.handlers.connect.async_session_factory") as session_factory:
        session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        await handle_telegram_channel_chat_id(message, state, bot)

    channel_repo = get_telegram_channel_repository(session)
    stored = await channel_repo.get_by_telegram_chat_id(channel_id)
    assert stored is not None
    assert stored.title == "Persisted Channel"
    assert stored.is_active is True
    message.answer.assert_awaited_once()
    assert SUCCESS_TEMPLATE.split("{")[0] in message.answer.await_args.args[0]
