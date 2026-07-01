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


class OrganizationPlan(str, enum.Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class InviteStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class OrganizationSecretType(str, enum.Enum):
    OPENROUTER = "openrouter"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"


class UsageMetric(str, enum.Enum):
    AI_COST_USD = "ai_cost_usd"
    AI_REQUESTS = "ai_requests"
    LLM_TOKENS = "llm_tokens"
    JOIN_REQUESTS = "join_requests"
    CHANNELS = "channels"
    USERS = "users"
    STORAGE_MB = "storage_mb"


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
