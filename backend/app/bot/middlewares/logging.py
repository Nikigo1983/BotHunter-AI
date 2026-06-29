from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.utils.logging import get_logger

logger = get_logger(__name__)


class IncomingMessageLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            user = event.from_user
            telegram_id = user.id if user else "unknown"
            username = user.username if user and user.username else "—"
            text = event.text or event.caption or "—"

            logger.info(
                "Incoming message | Telegram ID: %s | Username: %s | Text: %s",
                telegram_id,
                username,
                text,
            )

        return await handler(event, data)
