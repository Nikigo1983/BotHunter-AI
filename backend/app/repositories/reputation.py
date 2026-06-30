import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reputation import Reputation
from app.repositories.base import BaseRepository
from app.reputation.engine import DEFAULT_TRUST_SCORE


class ReputationRepository(BaseRepository[Reputation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Reputation)

    async def get_by_telegram_user_id(self, telegram_user_id: uuid.UUID) -> Reputation | None:
        stmt = select(Reputation).where(Reputation.telegram_user_id == telegram_user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, telegram_user_id: uuid.UUID) -> Reputation:
        existing = await self.get_by_telegram_user_id(telegram_user_id)
        if existing is not None:
            return existing
        return await self.create(
            Reputation(
                telegram_user_id=telegram_user_id,
                reputation_score=DEFAULT_TRUST_SCORE,
            )
        )
