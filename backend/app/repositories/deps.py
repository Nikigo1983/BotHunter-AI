from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.ai_feedback import AIFeedbackRepository
from app.repositories.admin_dashboard import AdminDashboardRepository
from app.repositories.analytics import AnalyticsRepository
from app.repositories.ai_analysis import AIAnalysisRepository
from app.repositories.ai_usage import AIUsageRepository
from app.repositories.analytics import AnalyticsRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.base import BaseRepository
from app.repositories.blacklist import BlacklistRepository
from app.repositories.channel import ChannelRepository
from app.repositories.channel_connection_error import ChannelConnectionErrorRepository
from app.repositories.channel_settings import ChannelSettingsRepository
from app.repositories.channel_statistics import ChannelStatisticsRepository
from app.repositories.join_request import JoinRequestRepository
from app.repositories.manual_review import ManualReviewRepository
from app.repositories.reputation import ReputationRepository
from app.repositories.reputation_history import ReputationHistoryRepository
from app.repositories.telegram_bot import TelegramBotRepository
from app.repositories.telegram_channel import TelegramChannelRepository
from app.repositories.telegram_user import TelegramUserRepository
from app.repositories.user import UserRepository
from app.repositories.whitelist import WhitelistRepository


def get_user_repository(session: AsyncSession) -> UserRepository:
    return UserRepository(session)


def get_telegram_bot_repository(session: AsyncSession) -> TelegramBotRepository:
    return TelegramBotRepository(session)


def get_telegram_channel_repository(session: AsyncSession) -> TelegramChannelRepository:
    return TelegramChannelRepository(session)


def get_channel_repository(session: AsyncSession) -> ChannelRepository:
    return ChannelRepository(session)


def get_telegram_user_repository(session: AsyncSession) -> TelegramUserRepository:
    return TelegramUserRepository(session)


def get_manual_review_repository(session: AsyncSession) -> ManualReviewRepository:
    return ManualReviewRepository(session)


def get_ai_feedback_repository(session: AsyncSession) -> AIFeedbackRepository:
    return AIFeedbackRepository(session)


def get_join_request_repository(session: AsyncSession) -> JoinRequestRepository:
    return JoinRequestRepository(session)


def get_ai_analysis_repository(session: AsyncSession) -> AIAnalysisRepository:
    return AIAnalysisRepository(session)


def get_admin_dashboard_repository(session: AsyncSession) -> AdminDashboardRepository:
    return AdminDashboardRepository(session)


def get_blacklist_repository(session: AsyncSession) -> BlacklistRepository:
    return BlacklistRepository(session)


def get_whitelist_repository(session: AsyncSession) -> WhitelistRepository:
    return WhitelistRepository(session)


def get_reputation_history_repository(session: AsyncSession) -> ReputationHistoryRepository:
    return ReputationHistoryRepository(session)


def get_reputation_repository(session: AsyncSession) -> ReputationRepository:
    return ReputationRepository(session)


def get_ai_usage_repository(session: AsyncSession) -> AIUsageRepository:
    return AIUsageRepository(session)


def get_analytics_repository(session: AsyncSession) -> AnalyticsRepository:
    return AnalyticsRepository(session)


def get_audit_log_repository(session: AsyncSession) -> AuditLogRepository:
    return AuditLogRepository(session)


def get_channel_connection_error_repository(
    session: AsyncSession,
) -> ChannelConnectionErrorRepository:
    return ChannelConnectionErrorRepository(session)


def get_channel_settings_repository(session: AsyncSession) -> ChannelSettingsRepository:
    return ChannelSettingsRepository(session)


def get_channel_statistics_repository(session: AsyncSession) -> ChannelStatisticsRepository:
    return ChannelStatisticsRepository(session)


RepositoryFactory = Callable[[AsyncSession], BaseRepository]
