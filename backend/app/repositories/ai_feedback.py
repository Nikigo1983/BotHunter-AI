import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_feedback import AIFeedback
from app.repositories.base import BaseRepository


class AIFeedbackRepository(BaseRepository[AIFeedback]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AIFeedback)

    async def list_by_join_request_id(self, join_request_id: uuid.UUID) -> list[AIFeedback]:
        stmt = (
            select(AIFeedback)
            .where(AIFeedback.join_request_id == join_request_id)
            .order_by(AIFeedback.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
