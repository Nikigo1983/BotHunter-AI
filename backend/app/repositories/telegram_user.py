from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_user import TelegramUser
from app.repositories.base import BaseRepository


class TelegramUserRepository(BaseRepository[TelegramUser]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TelegramUser)
