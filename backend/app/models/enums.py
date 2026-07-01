import enum


class JoinRequestStatus(str, enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    MANUAL_REVIEW = "ManualReview"


class AnalysisDecision(str, enum.Enum):
    APPROVED = "Approved"
    REJECTED = "Rejected"
    MANUAL_REVIEW = "ManualReview"


class DashboardRole(str, enum.Enum):
    OWNER = "owner"
    ADMINISTRATOR = "administrator"
    MODERATOR = "moderator"
    VIEWER = "viewer"


class SystemErrorSource(str, enum.Enum):
    TELEGRAM = "telegram"
    OPENROUTER = "openrouter"
    SQL = "sql"
    REDIS = "redis"
    API = "api"
    BOT = "bot"


class NotificationLevel(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
