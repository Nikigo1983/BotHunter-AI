from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_user import TelegramUser
from app.repositories.base import BaseRepository


class TelegramUserRepository(BaseRepository[TelegramUser]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TelegramUser)

    async def get_by_telegram_id(self, telegram_id: int) -> TelegramUser | None:
        stmt = select(TelegramUser).where(TelegramUser.telegram_id == telegram_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
