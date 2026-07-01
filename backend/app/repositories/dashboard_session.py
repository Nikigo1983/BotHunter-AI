from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard_session import DashboardSession
from app.repositories.base import BaseRepository


class DashboardSessionRepository(BaseRepository[DashboardSession]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DashboardSession)

    async def get_by_token_hash(self, token_hash: str) -> DashboardSession | None:
        stmt = select(DashboardSession).where(DashboardSession.token_hash == token_hash)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_by_token_hash(self, token_hash: str) -> None:
        stmt = delete(DashboardSession).where(DashboardSession.token_hash == token_hash)
        await self._session.execute(stmt)
        await self._session.flush()

    async def delete_expired(self) -> int:
        stmt = delete(DashboardSession).where(DashboardSession.expires_at < datetime.now(UTC))
        result = await self._session.execute(stmt)
        await self._session.flush()
        return int(result.rowcount or 0)
