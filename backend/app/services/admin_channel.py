import uuid
from typing import Any

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel_settings import ChannelSettings
from app.models.telegram_channel import TelegramChannel
from app.repositories.channel_settings import ChannelSettingsRepository
from app.repositories.channel_statistics import ChannelStatisticsRepository
from app.repositories.deps import (
    get_channel_repository,
    get_channel_settings_repository,
    get_channel_statistics_repository,
)
from app.schemas.channel_management import (
    ChannelDetailDTO,
    ChannelListItemDTO,
    ChannelRecentRequestDTO,
    ChannelSettingsDTO,
    ChannelSettingsUpdateRequest,
    ChannelTimelinePointDTO,
)


class AdminChannelService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        stats_repo: ChannelStatisticsRepository | None = None,
        settings_repo: ChannelSettingsRepository | None = None,
    ) -> None:
        self._session = session
        self._stats_repo = stats_repo or get_channel_statistics_repository(session)
        self._settings_repo = settings_repo or get_channel_settings_repository(session)
        self._channel_repo = get_channel_repository(session)

    async def list_channels(self) -> list[ChannelListItemDTO]:
        rows = await self._stats_repo.list_channel_summaries()
        return [self._map_list_item(row) for row in rows]

    async def get_channel_detail(
        self,
        channel_id: uuid.UUID,
        *,
        timeline_days: int = 30,
        bot: Bot | None = None,
    ) -> ChannelDetailDTO | None:
        summary = await self._stats_repo.get_channel_summary(channel_id)
        if summary is None:
            return None

        channel = await self._stats_repo.get_channel(channel_id)
        if channel is None:
            return None

        settings = await self._settings_repo.get_or_create(channel_id)
        accuracy = await self._stats_repo.get_channel_accuracy(channel_id)
        recent = await self._stats_repo.list_recent_join_requests(channel_id, limit=20)
        safe_days = timeline_days if timeline_days in {7, 30, 90} else 30
        timeline = await self._stats_repo.get_timeline(channel_id, days=safe_days)
        member_count = await self._fetch_member_count(channel, bot)

        return ChannelDetailDTO(
            id=channel.id,
            title=channel.title,
            telegram_chat_id=channel.telegram_chat_id,
            username=channel.username,
            is_active=channel.is_active,
            created_at=channel.created_at,
            invite_link=channel.invite_link,
            last_activity_at=summary.get("last_activity_at"),
            member_count=member_count,
            total_requests=int(summary.get("total_requests") or 0),
            approved=int(summary.get("approved") or 0),
            rejected=int(summary.get("rejected") or 0),
            manual_review=int(summary.get("manual_review") or 0),
            pending=int(summary.get("pending") or 0),
            whitelist_count=int(summary.get("whitelist_count") or 0),
            blacklist_count=int(summary.get("blacklist_count") or 0),
            avg_rule_score=self._optional_float(summary.get("avg_rule_score")),
            avg_ai_score=self._optional_float(summary.get("avg_ai_score")),
            avg_trust_score=self._optional_float(summary.get("avg_trust_score")),
            ai_accuracy_percent=accuracy.get("accuracy_percent"),
            settings=self._map_settings(settings),
            recent_requests=[self._map_recent_request(item) for item in recent],
            timeline=[self._map_timeline_point(row) for row in timeline],
        )

    async def get_statistics(self, channel_id: uuid.UUID) -> dict[str, Any] | None:
        summary = await self._stats_repo.get_channel_summary(channel_id)
        if summary is None:
            return None
        accuracy = await self._stats_repo.get_channel_accuracy(channel_id)
        return {
            "total_requests": int(summary.get("total_requests") or 0),
            "approved": int(summary.get("approved") or 0),
            "rejected": int(summary.get("rejected") or 0),
            "manual_review": int(summary.get("manual_review") or 0),
            "pending": int(summary.get("pending") or 0),
            "whitelist_count": int(summary.get("whitelist_count") or 0),
            "blacklist_count": int(summary.get("blacklist_count") or 0),
            "avg_rule_score": self._optional_float(summary.get("avg_rule_score")),
            "avg_ai_score": self._optional_float(summary.get("avg_ai_score")),
            "avg_trust_score": self._optional_float(summary.get("avg_trust_score")),
            "ai_accuracy_percent": accuracy.get("accuracy_percent"),
            "last_activity_at": summary.get("last_activity_at"),
        }

    async def update_channel(
        self,
        channel_id: uuid.UUID,
        payload: ChannelSettingsUpdateRequest,
    ) -> ChannelDetailDTO | None:
        channel = await self._stats_repo.get_channel(channel_id)
        if channel is None:
            return None

        settings = await self._settings_repo.get_or_create(channel_id)
        updates = payload.model_dump(exclude_unset=True)
        is_active = updates.pop("is_active", None)

        for field, value in updates.items():
            setattr(settings, field, value)
        await self._settings_repo.update(settings)

        if is_active is not None:
            channel.is_active = is_active
            await self._channel_repo.update(channel)

        return await self.get_channel_detail(channel_id)

    async def set_channel_active(
        self,
        channel_id: uuid.UUID,
        *,
        is_active: bool,
    ) -> ChannelDetailDTO | None:
        return await self.update_channel(
            channel_id,
            ChannelSettingsUpdateRequest(is_active=is_active),
        )

    @staticmethod
    async def _fetch_member_count(channel: TelegramChannel, bot: Bot | None) -> int | None:
        if bot is None:
            return None
        try:
            return await bot.get_chat_member_count(channel.telegram_chat_id)
        except Exception:
            return None

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        return round(float(value), 2)

    @staticmethod
    def _map_settings(settings: ChannelSettings) -> ChannelSettingsDTO:
        return ChannelSettingsDTO(
            ai_enabled=settings.ai_enabled,
            rule_auto_approve=settings.rule_auto_approve,
            rule_auto_reject=settings.rule_auto_reject,
            trust_auto_approve=settings.trust_auto_approve,
            trust_auto_reject=settings.trust_auto_reject,
            join_request_timeout_hours=settings.join_request_timeout_hours,
        )

    @staticmethod
    def _map_list_item(row: dict[str, Any]) -> ChannelListItemDTO:
        return ChannelListItemDTO(
            id=row["id"],
            title=row["title"],
            telegram_chat_id=int(row["telegram_chat_id"]),
            username=row.get("username"),
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            total_requests=int(row.get("total_requests") or 0),
            approved=int(row.get("approved") or 0),
            rejected=int(row.get("rejected") or 0),
            manual_review=int(row.get("manual_review") or 0),
            avg_rule_score=AdminChannelService._optional_float(row.get("avg_rule_score")),
            avg_ai_score=AdminChannelService._optional_float(row.get("avg_ai_score")),
            avg_trust_score=AdminChannelService._optional_float(row.get("avg_trust_score")),
        )

    @staticmethod
    def _map_recent_request(item) -> ChannelRecentRequestDTO:
        analysis = max(item.ai_analyses, key=lambda row: row.created_at) if item.ai_analyses else None
        return ChannelRecentRequestDTO(
            id=item.id,
            created_at=item.created_at,
            telegram_id=item.telegram_user.telegram_id,
            username=item.telegram_user.username,
            status=item.status.value,
            rule_score=analysis.rule_score if analysis else None,
            ai_score=analysis.ai_score if analysis else None,
            final_score=analysis.final_score if analysis else None,
        )

    @staticmethod
    def _map_timeline_point(row: dict[str, Any]) -> ChannelTimelinePointDTO:
        return ChannelTimelinePointDTO(
            date=str(row["date"]),
            total_requests=int(row.get("total_requests") or 0),
            approved=int(row.get("approved") or 0),
            rejected=int(row.get("rejected") or 0),
            manual_review=int(row.get("manual_review") or 0),
            accuracy_percent=(
                float(row["accuracy_percent"]) if row.get("accuracy_percent") is not None else None
            ),
            feedback_count=int(row.get("feedback_count") or 0),
            ai_calls=int(row.get("ai_calls") or 0),
            ai_cost=float(row.get("ai_cost") or 0.0),
        )
