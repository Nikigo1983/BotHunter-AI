from sqlalchemy.ext.asyncio import AsyncSession

from app.models.whitelist import Whitelist
from app.repositories.base import BaseRepository


class WhitelistRepository(BaseRepository[Whitelist]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Whitelist)
