import enum


class ReputationChangeReason(str, enum.Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WHITELISTED = "WHITELISTED"
    BLACKLISTED = "BLACKLISTED"
    MANUAL_APPROVED = "MANUAL_APPROVED"
    MANUAL_REJECTED = "MANUAL_REJECTED"


class ReputationTrend(str, enum.Enum):
    UP = "UP"
    DOWN = "DOWN"
    STABLE = "STABLE"
