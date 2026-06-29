from sqlalchemy.ext.asyncio import AsyncSession

from app.models.join_request import JoinRequest
from app.repositories.base import BaseRepository


class JoinRequestRepository(BaseRepository[JoinRequest]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, JoinRequest)
