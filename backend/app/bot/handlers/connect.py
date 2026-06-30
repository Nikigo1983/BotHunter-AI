import re
from typing import Final

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.states.connect import ConnectChannelStates
from app.database.session import async_session_factory
from app.services.channel_registration import ChannelRegistrationService
from app.services.channel_registration_types import (
    ChannelRegistrationFailure,
    ChannelRegistrationSuccess,
)

router = Router(name="connect")

TELEGRAM_CHANNEL_CHAT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^-100\d+$")

CONNECT_INSTRUCTIONS = (
    "🔗 Подключение Telegram-канала\n\n"
    "Чтобы подключить канал к BotHunter AI, выполните шаги:\n\n"
    "1. Добавьте BotHunter AI в администраторы канала.\n\n"
    "2. Выдайте права:\n"
    "• Invite Users\n"
    "• Manage Join Requests\n\n"
    "3. Отправьте боту ID канала.\n\n"
    "Пример ID: -1001234567890"
)

SUCCESS_TEMPLATE = (
    "✅ Канал успешно подключён.\n\n"
    "Название:\n"
    "{title}\n\n"
    "ID:\n"
    "{channel_id}\n\n"
    "Статус:\n"
    "Активен."
)

FAILURE_TEMPLATE = (
    "❌ Не удалось подключить канал.\n\n"
    "Причина:\n"
    "{reason}"
)


def is_telegram_channel_chat_id(text: str | None) -> bool:
    if not text:
        return False
    return TELEGRAM_CHANNEL_CHAT_ID_PATTERN.fullmatch(text.strip()) is not None


@router.message(Command("connect"))
async def handle_connect(message: Message, state: FSMContext) -> None:
    await state.set_state(ConnectChannelStates.waiting_for_channel_id)
    await message.answer(CONNECT_INSTRUCTIONS)


@router.message(F.text.func(lambda text: is_telegram_channel_chat_id(text)))
async def handle_telegram_channel_chat_id(
    message: Message,
    state: FSMContext,
    bot: Bot,
) -> None:
    if message.from_user is None or message.text is None:
        return

    async with async_session_factory() as session:
        service = ChannelRegistrationService(session, bot)
        result = await service.register_channel(
            requester=message.from_user,
            channel_id_raw=message.text.strip(),
        )
        await session.commit()

    await state.clear()

    if isinstance(result, ChannelRegistrationSuccess):
        await message.answer(
            SUCCESS_TEMPLATE.format(
                title=result.title,
                channel_id=result.telegram_chat_id,
            )
        )
        return

    if isinstance(result, ChannelRegistrationFailure):
        await message.answer(FAILURE_TEMPLATE.format(reason=result.reason))
