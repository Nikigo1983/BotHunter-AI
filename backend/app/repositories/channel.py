import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_channel import TelegramChannel
from app.repositories.telegram_channel import TelegramChannelRepository


class ChannelRepository(TelegramChannelRepository):
    """Channel CRUD facade used by admin channel management."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_all(self) -> list[TelegramChannel]:
        stmt = select(TelegramChannel).order_by(TelegramChannel.created_at.desc())
        return list((await self._session.execute(stmt)).scalars().all())

    async def set_active(self, channel_id: uuid.UUID, *, is_active: bool) -> TelegramChannel | None:
        channel = await self.get_by_id(channel_id)
        if channel is None:
            return None
        channel.is_active = is_active
        return await self.update(channel)
