from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_bot import TelegramBot
from app.repositories.base import BaseRepository


class TelegramBotRepository(BaseRepository[TelegramBot]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TelegramBot)

    async def get_by_bot_username(self, bot_username: str) -> TelegramBot | None:
        stmt = select(TelegramBot).where(TelegramBot.bot_username == bot_username)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
