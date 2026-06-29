from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_channel import TelegramChannel
from app.repositories.base import BaseRepository


class TelegramChannelRepository(BaseRepository[TelegramChannel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TelegramChannel)

    async def get_by_telegram_chat_id(self, telegram_chat_id: int) -> TelegramChannel | None:
        stmt = select(TelegramChannel).where(
            TelegramChannel.telegram_chat_id == telegram_chat_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
