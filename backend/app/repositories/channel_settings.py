import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.decision_settings import DecisionThresholds
from app.models.channel_settings import ChannelSettings
from app.repositories.base import BaseRepository


class ChannelSettingsRepository(BaseRepository[ChannelSettings]):
    DEFAULTS = {
        "ai_enabled": True,
        "rule_auto_approve": DecisionThresholds().approve_below,
        "rule_auto_reject": DecisionThresholds().reject_from,
        "trust_auto_approve": 90,
        "trust_auto_reject": 10,
        "join_request_timeout_hours": None,
    }

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ChannelSettings)

    async def get_by_channel_id(self, channel_id: uuid.UUID) -> ChannelSettings | None:
        stmt = select(ChannelSettings).where(ChannelSettings.channel_id == channel_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_create(self, channel_id: uuid.UUID) -> ChannelSettings:
        existing = await self.get_by_channel_id(channel_id)
        if existing is not None:
            return existing
        return await self.create(ChannelSettings(channel_id=channel_id, **self.DEFAULTS))
