from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_error import SystemError
from app.repositories.base import BaseRepository


class SystemErrorRepository(BaseRepository[SystemError]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SystemError)

    async def list_recent(self, *, limit: int = 100, source: str | None = None) -> list[SystemError]:
        stmt = select(SystemError).order_by(desc(SystemError.created_at)).limit(limit)
        if source:
            stmt = stmt.where(SystemError.source == source)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_unresolved(self) -> int:
        stmt = select(func.count()).select_from(SystemError).where(SystemError.resolved.is_(False))
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def count_by_source(self) -> dict[str, int]:
        stmt = (
            select(SystemError.source, func.count())
            .where(SystemError.resolved.is_(False))
            .group_by(SystemError.source)
        )
        result = await self._session.execute(stmt)
        return {source: int(count) for source, count in result.all()}
