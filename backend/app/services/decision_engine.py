import json

from app.config.decision_settings import DecisionThresholds, get_decision_thresholds
from app.models.enums import AnalysisDecision


class DecisionEngine:
    def __init__(self, thresholds: DecisionThresholds | None = None) -> None:
        self._thresholds = thresholds or get_decision_thresholds()

    @property
    def thresholds(self) -> DecisionThresholds:
        return self._thresholds

    def decide(self, rule_score: int) -> AnalysisDecision:
        if rule_score < self._thresholds.approve_below:
            return AnalysisDecision.APPROVED
        if rule_score < self._thresholds.reject_from:
            return AnalysisDecision.MANUAL_REVIEW
        return AnalysisDecision.REJECTED

    @staticmethod
    def map_to_join_request_status(decision: AnalysisDecision):
        from app.models.enums import JoinRequestStatus

        mapping = {
            AnalysisDecision.APPROVED: JoinRequestStatus.APPROVED,
            AnalysisDecision.REJECTED: JoinRequestStatus.REJECTED,
            AnalysisDecision.MANUAL_REVIEW: JoinRequestStatus.MANUAL_REVIEW,
        }
        return mapping[decision]
