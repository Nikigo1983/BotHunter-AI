from aiogram import Bot, Router
from aiogram.enums import ChatType, MessageOriginType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Chat, Message, MessageOriginChannel, MessageOriginChat

from app.bot.states.debug_chatid import DebugChatIdStates

router = Router(name="debug_chatid")

PROMPT_TEXT = "Перешлите любое сообщение из канала."


@router.message(Command("debug_chatid"))
async def handle_debug_chatid(message: Message, state: FSMContext) -> None:
    await state.set_state(DebugChatIdStates.waiting_for_forward)
    await message.answer(PROMPT_TEXT)


@router.message(StateFilter(DebugChatIdStates.waiting_for_forward))
async def handle_forwarded_channel_message(
    message: Message,
    state: FSMContext,
    bot: Bot,
) -> None:
    await state.clear()

    source_chat, reason = _resolve_forward_source(message)
    if source_chat is None:
        await message.answer(reason or "Не удалось определить источник пересылки.")
        return

    bot_access = await _check_bot_channel_access(bot, source_chat.id)
    chat_type_label = _format_chat_type(source_chat.type)

    await message.answer(
        "🔍 Debug: данные канала из пересылки\n\n"
        f"Chat ID:\n`{source_chat.id}`\n\n"
        f"Chat title:\n{source_chat.title or '—'}\n\n"
        f"Chat type:\n{chat_type_label}\n\n"
        f"Доступ бота к каналу:\n{bot_access}",
        parse_mode="Markdown",
    )


def _resolve_forward_source(message: Message) -> tuple[Chat | None, str | None]:
    origin = message.forward_origin

    if origin is not None:
        if isinstance(origin, MessageOriginChannel):
            return origin.chat, None

        if isinstance(origin, MessageOriginChat):
            if origin.chat.type != ChatType.CHANNEL:
                return None, (
                    "Пересылка пришла из чата/группы, а не из канала.\n"
                    f"Тип источника: {_format_chat_type(origin.chat.type)}.\n"
                    "Перешлите сообщение именно из канала (Channel)."
                )
            return origin.chat, None

        if origin.type == MessageOriginType.USER:
            return None, (
                "Сообщение переслано от пользователя, а не из канала.\n"
                "Перешлите пост из нужного канала через «Переслать»."
            )

        if origin.type == MessageOriginType.HIDDEN_USER:
            return None, (
                "Telegram скрыл данные об отправителе (privacy settings).\n"
                "Бот не получил Chat ID канала. Попробуйте другой пост "
                "или отправьте ID канала вручную через /connect."
            )

        if origin.type == MessageOriginType.CHAT:
            return None, (
                "Telegram передал только тип «chat» без канала.\n"
                "Убедитесь, что пересылаете сообщение из публичного канала."
            )

    if message.forward_from_chat is not None:
        chat = message.forward_from_chat
        if chat.type != ChatType.CHANNEL:
            return None, (
                "Пересылка не из канала.\n"
                f"Тип источника: {_format_chat_type(chat.type)}."
            )
        return chat, None

    if message.forward_from is not None:
        return None, (
            "Сообщение переслано от пользователя, а не из канала.\n"
            "Перешлите пост из канала."
        )

    if message.forward_sender_name:
        return None, (
            "Telegram не передал Chat ID источника (только имя отправителя).\n"
            "Частая причина — скрытая пересылка или ограничения приватности канала."
        )

    if not (message.forward_date or message.forward_signature):
        return None, (
            "Это не пересланное сообщение.\n"
            "Сначала выполните /debug_chatid, затем перешлите пост из канала."
        )

    return None, (
        "Telegram не передал данные о канале в пересылке.\n"
        "Возможные причины:\n"
        "• сообщение не из канала;\n"
        "• включена защита контента / скрыта пересылка;\n"
        "• у канала ограничена видимость метаданных для ботов."
    )


async def _check_bot_channel_access(bot: Bot, chat_id: int) -> str:
    try:
        chat = await bot.get_chat(chat_id)
    except TelegramBadRequest as exc:
        return (
            "Нет — бот не может получить информацию о канале.\n"
            f"Причина: {exc.message}"
        )
    except Exception as exc:
        return f"Нет — ошибка при запросе: {exc}"

    title = chat.title or "—"
    username = f"@{chat.username}" if chat.username else "нет public username"
    return (
        "Да — бот получил информацию о канале.\n"
        f"Title из API: {title}\n"
        f"Username: {username}"
    )


def _format_chat_type(chat_type: str | ChatType) -> str:
    labels = {
        ChatType.PRIVATE: "private",
        ChatType.GROUP: "group",
        ChatType.SUPERGROUP: "supergroup",
        ChatType.CHANNEL: "channel",
    }
    if isinstance(chat_type, ChatType):
        return labels.get(chat_type, chat_type.value)
    return str(chat_type)
