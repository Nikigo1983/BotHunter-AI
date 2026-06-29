import pytest

from app.config.decision_settings import DecisionThresholds
from app.models.enums import AnalysisDecision
from app.services.decision_engine import DecisionEngine


@pytest.fixture
def decision_engine() -> DecisionEngine:
    return DecisionEngine(
        DecisionThresholds(approve_below=30, reject_from=70),
    )


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, AnalysisDecision.APPROVED),
        (29, AnalysisDecision.APPROVED),
        (30, AnalysisDecision.MANUAL_REVIEW),
        (69, AnalysisDecision.MANUAL_REVIEW),
        (70, AnalysisDecision.REJECTED),
        (100, AnalysisDecision.REJECTED),
    ],
)
def test_decision_engine_thresholds(
    decision_engine: DecisionEngine,
    score: int,
    expected: AnalysisDecision,
) -> None:
    assert decision_engine.decide(score) == expected


def test_decision_engine_maps_to_join_request_status(decision_engine: DecisionEngine) -> None:
    from app.models.enums import JoinRequestStatus

    assert (
        decision_engine.map_to_join_request_status(AnalysisDecision.APPROVED)
        == JoinRequestStatus.APPROVED
    )
    assert (
        decision_engine.map_to_join_request_status(AnalysisDecision.MANUAL_REVIEW)
        == JoinRequestStatus.MANUAL_REVIEW
    )
    assert (
        decision_engine.map_to_join_request_status(AnalysisDecision.REJECTED)
        == JoinRequestStatus.REJECTED
    )
