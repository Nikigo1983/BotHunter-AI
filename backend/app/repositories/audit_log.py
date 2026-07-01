from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AuditLog)

    async def list_by_entity(
        self,
        *,
        entity: str,
        entity_id,
        limit: int = 200,
    ) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.entity == entity, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.created_at.asc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())
