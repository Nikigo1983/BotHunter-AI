from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reputation import Reputation
from app.repositories.base import BaseRepository


class ReputationRepository(BaseRepository[Reputation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Reputation)
