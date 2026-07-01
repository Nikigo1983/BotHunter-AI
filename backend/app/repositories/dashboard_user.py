from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard_user import DashboardUser
from app.repositories.base import BaseRepository


class DashboardUserRepository(BaseRepository[DashboardUser]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DashboardUser)

    async def get_by_email(self, email: str) -> DashboardUser | None:
        stmt = select(DashboardUser).where(DashboardUser.email == email.lower().strip())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_all(self) -> int:
        stmt = select(func.count()).select_from(DashboardUser)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())
