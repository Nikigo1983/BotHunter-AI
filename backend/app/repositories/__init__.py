from app.repositories.ai_analysis import AIAnalysisRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.base import BaseRepository
from app.repositories.blacklist import BlacklistRepository
from app.repositories.channel_connection_error import ChannelConnectionErrorRepository
from app.repositories.deps import (
    get_ai_analysis_repository,
    get_audit_log_repository,
    get_blacklist_repository,
    get_channel_connection_error_repository,
    get_join_request_repository,
    get_reputation_repository,
    get_telegram_bot_repository,
    get_telegram_channel_repository,
    get_telegram_user_repository,
    get_user_repository,
    get_whitelist_repository,
)
from app.repositories.join_request import JoinRequestRepository
from app.repositories.reputation import ReputationRepository
from app.repositories.telegram_bot import TelegramBotRepository
from app.repositories.telegram_channel import TelegramChannelRepository
from app.repositories.telegram_user import TelegramUserRepository
from app.repositories.user import UserRepository
from app.repositories.whitelist import WhitelistRepository

__all__ = [
    "AIAnalysisRepository",
    "AuditLogRepository",
    "BaseRepository",
    "BlacklistRepository",
    "ChannelConnectionErrorRepository",
    "JoinRequestRepository",
    "ReputationRepository",
    "TelegramBotRepository",
    "TelegramChannelRepository",
    "TelegramUserRepository",
    "UserRepository",
    "WhitelistRepository",
    "get_ai_analysis_repository",
    "get_audit_log_repository",
    "get_blacklist_repository",
    "get_channel_connection_error_repository",
    "get_join_request_repository",
    "get_reputation_repository",
    "get_telegram_bot_repository",
    "get_telegram_channel_repository",
    "get_telegram_user_repository",
    "get_user_repository",
    "get_whitelist_repository",
]
