import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.token import TokenValidationError, validate_token

from app.bot.handlers import commands_router, connect_router
from app.bot.middlewares import IncomingMessageLoggingMiddleware
from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

PLACEHOLDER_TOKENS = frozenset({"", "your-telegram-bot-token"})


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(IncomingMessageLoggingMiddleware())
    dp.include_router(commands_router)
    dp.include_router(connect_router)
    return dp


def is_bot_token_configured() -> bool:
    settings = get_settings()
    token = settings.bot_token.strip()
    if token in PLACEHOLDER_TOKENS:
        return False
    try:
        validate_token(token)
    except TokenValidationError:
        return False
    return True


def create_bot() -> Bot:
    settings = get_settings()
    if not is_bot_token_configured():
        raise ValueError("BOT_TOKEN is not configured or invalid")
    return Bot(token=settings.bot_token)


async def start_bot() -> None:
    if not is_bot_token_configured():
        logger.warning(
            "BOT_TOKEN is missing or invalid. Bot service is idle. "
            "Set a valid BOT_TOKEN in .env to enable polling."
        )
        await asyncio.Event().wait()
        return

    bot = create_bot()
    dp = create_dispatcher()

    logger.info("Starting Telegram bot polling")
    await dp.start_polling(bot)

