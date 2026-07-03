from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_notification import SystemNotification
from app.repositories.deps import get_system_notification_repository


@dataclass(slots=True)
class NotificationDTO:
    id: str
    level: str
    title: str
    message: str
    source: str
    created_at: datetime
    is_read: bool


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = get_system_notification_repository(session)

    async def get_active_alerts(self, *, limit: int = 10) -> list[NotificationDTO]:
        rows = await self._repo.list_unread(limit=limit)
        return [self._to_dto(row) for row in rows]

    async def list_all(self, *, limit: int = 50) -> list[NotificationDTO]:
        rows = await self._repo.list_recent(limit=limit)
        return [self._to_dto(row) for row in rows]

    async def mark_all_read(self) -> None:
        await self._repo.mark_all_read()

    async def resolve_alerts_for_source(self, source: str) -> None:
        await self._repo.mark_read_by_source(source)

    async def ensure_alert(
        self,
        *,
        level: str,
        title: str,
        message: str,
        source: str,
    ) -> None:
        from sqlalchemy import desc

        stmt = (
            select(SystemNotification)
            .where(SystemNotification.source == source)
            .where(SystemNotification.is_read.is_(False))
            .order_by(desc(SystemNotification.created_at))
            .limit(1)
        )
        result = await self._repo.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None and existing.title == title:
            return
        await self._repo.create(
            SystemNotification(
                level=level,
                title=title,
                message=message,
                source=source,
                is_read=False,
            )
        )

    @staticmethod
    def _to_dto(row: SystemNotification) -> NotificationDTO:
        return NotificationDTO(
            id=str(row.id),
            level=row.level,
            title=row.title,
            message=row.message,
            source=row.source,
            created_at=row.created_at,
            is_read=row.is_read,
        )
