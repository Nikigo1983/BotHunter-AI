from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting
from app.repositories.base import BaseRepository


class SystemSettingRepository(BaseRepository[SystemSetting]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SystemSetting)

    async def get_by_key(self, key: str) -> SystemSetting | None:
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_settings(self) -> dict[str, str]:
        stmt = select(SystemSetting)
        result = await self._session.execute(stmt)
        return {row.key: row.value for row in result.scalars().all()}

    async def upsert(self, key: str, value: str, *, updated_by: str | None = None) -> SystemSetting:
        existing = await self.get_by_key(key)
        if existing is None:
            entity = SystemSetting(key=key, value=value, updated_by=updated_by)
            return await self.create(entity)
        existing.value = value
        existing.updated_by = updated_by
        return await self.update(existing)
