from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_notification import SystemNotification
from app.repositories.base import BaseRepository


class SystemNotificationRepository(BaseRepository[SystemNotification]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SystemNotification)

    async def list_unread(self, *, limit: int = 20) -> list[SystemNotification]:
        stmt = (
            select(SystemNotification)
            .where(SystemNotification.is_read.is_(False))
            .order_by(desc(SystemNotification.created_at))
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_recent(self, *, limit: int = 50) -> list[SystemNotification]:
        stmt = select(SystemNotification).order_by(desc(SystemNotification.created_at)).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_unread_critical(self) -> int:
        stmt = (
            select(func.count())
            .select_from(SystemNotification)
            .where(SystemNotification.is_read.is_(False))
            .where(SystemNotification.level == "critical")
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def mark_all_read(self) -> None:
        stmt = update(SystemNotification).values(is_read=True).where(
            SystemNotification.is_read.is_(False)
        )
        await self._session.execute(stmt)
        await self._session.flush()
