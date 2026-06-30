import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manual_review import ManualReview
from app.repositories.base import BaseRepository


class ManualReviewRepository(BaseRepository[ManualReview]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ManualReview)

    async def list_by_join_request_id(self, join_request_id: uuid.UUID) -> list[ManualReview]:
        stmt = (
            select(ManualReview)
            .where(ManualReview.join_request_id == join_request_id)
            .order_by(ManualReview.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
