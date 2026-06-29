from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blacklist import Blacklist
from app.repositories.base import BaseRepository


class BlacklistRepository(BaseRepository[Blacklist]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Blacklist)
