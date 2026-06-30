import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blacklist import Blacklist
from app.repositories.base import BaseRepository


class BlacklistRepository(BaseRepository[Blacklist]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Blacklist)

    async def get_by_telegram_user_id(self, telegram_user_id: uuid.UUID) -> Blacklist | None:
        stmt = select(Blacklist).where(Blacklist.telegram_user_id == telegram_user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_by_telegram_user_id(self, telegram_user_id: uuid.UUID) -> bool:
        return (await self.get_by_telegram_user_id(telegram_user_id)) is not None
