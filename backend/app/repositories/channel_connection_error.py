from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel_connection_error import ChannelConnectionError
from app.repositories.base import BaseRepository


class ChannelConnectionErrorRepository(BaseRepository[ChannelConnectionError]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ChannelConnectionError)
