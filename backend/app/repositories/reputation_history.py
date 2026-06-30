import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reputation_history import ReputationHistory
from app.repositories.base import BaseRepository


class ReputationHistoryRepository(BaseRepository[ReputationHistory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ReputationHistory)

    async def list_by_telegram_user_id(
        self,
        telegram_user_id: uuid.UUID,
        *,
        limit: int = 50,
    ) -> list[ReputationHistory]:
        stmt = (
            select(ReputationHistory)
            .where(ReputationHistory.telegram_user_id == telegram_user_id)
            .order_by(ReputationHistory.created_at.desc(), ReputationHistory.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
