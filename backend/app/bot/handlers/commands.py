from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="commands")

START_TEXT = (
    "👋 Добро пожаловать в BotHunter AI!\n\n"
    "Платформа запущена.\n\n"
    "Статус: Online."
)

HELP_TEXT = (
    "📋 Доступные команды:\n\n"
    "/start — приветствие и статус платформы\n"
    "/help — список доступных команд\n"
    "/connect — подключить Telegram-канал к BotHunter AI"
)


@router.message(Command("start"))
async def handle_start(message: Message) -> None:
    await message.answer(START_TEXT)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer(HELP_TEXT)
