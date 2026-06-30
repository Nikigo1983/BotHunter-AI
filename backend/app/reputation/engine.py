DEFAULT_TRUST_SCORE = 50.0
MIN_TRUST_SCORE = 0.0
MAX_TRUST_SCORE = 100.0

AUTO_APPROVE_THRESHOLD = 90.0
AUTO_REJECT_THRESHOLD = 10.0

APPROVE_DELTA = 5.0
REJECT_DELTA = 10.0
WHITELIST_SCORE = 100.0
BLACKLIST_SCORE = 0.0


class ReputationEngine:
    @staticmethod
    def clamp(score: float) -> float:
        return max(MIN_TRUST_SCORE, min(MAX_TRUST_SCORE, score))

    @staticmethod
    def increase(current: float, delta: float = APPROVE_DELTA) -> float:
        return ReputationEngine.clamp(current + delta)

    @staticmethod
    def decrease(current: float, delta: float = REJECT_DELTA) -> float:
        return ReputationEngine.clamp(current - delta)

    @staticmethod
    def set_whitelist() -> float:
        return WHITELIST_SCORE

    @staticmethod
    def set_blacklist() -> float:
        return BLACKLIST_SCORE

    @staticmethod
    def should_auto_approve(trust_score: float) -> bool:
        return trust_score >= AUTO_APPROVE_THRESHOLD

    @staticmethod
    def should_auto_reject(trust_score: float) -> bool:
        return trust_score <= AUTO_REJECT_THRESHOLD
