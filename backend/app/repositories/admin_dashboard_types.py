import uuid
from dataclasses import dataclass
from datetime import datetime

from app.models.ai_analysis import AIAnalysis
from app.models.enums import JoinRequestStatus
from app.models.join_request import JoinRequest
from app.models.telegram_channel import TelegramChannel
from app.models.telegram_user import TelegramUser


@dataclass(slots=True)
class JoinRequestAdminRow:
    join_request: JoinRequest
    channel: TelegramChannel
    telegram_user: TelegramUser
    analysis: AIAnalysis | None


@dataclass(slots=True)
class JoinRequestListQueryResult:
    rows: list[JoinRequestAdminRow]
    total: int
