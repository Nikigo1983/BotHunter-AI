import enum


class AIServiceStatus(str, enum.Enum):
    SKIPPED = "SKIPPED"
    SUCCESS = "SUCCESS"
    FALLBACK = "FALLBACK"
    UNAVAILABLE = "AI_UNAVAILABLE"
