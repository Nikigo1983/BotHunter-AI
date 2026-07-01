import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.features import FeatureExtractor
from app.models.enums import AnalysisDecision
from app.policy.types import PolicyThresholdConfig
from app.repositories.deps import get_policy_repository
from app.services.policy import PolicyService


@dataclass(slots=True)
class SimulationRequest:
    rule_key: str | None = None
    score: int | None = None
    enabled: bool | None = None
    thresholds: PolicyThresholdConfig | None = None
    sample_size: int = 100


@dataclass(slots=True)
class SimulationDecisionDelta:
    approved: int
    rejected: int
    manual_review: int


@dataclass(slots=True)
class SimulationResult:
    sample_size: int
    baseline: SimulationDecisionDelta
    simulated: SimulationDecisionDelta
    delta: SimulationDecisionDelta


class PolicySimulationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = get_policy_repository(session)
        self._policy_service = PolicyService(session)
        self._feature_extractor = FeatureExtractor()

    async def simulate(self, request: SimulationRequest) -> SimulationResult:
        baseline_policy = await self._policy_service.get_effective_policy()
        simulated_policy = baseline_policy
        if request.rule_key:
            simulated_policy = baseline_policy.with_rule_override(
                request.rule_key,
                score=request.score,
                enabled=request.enabled,
            )
        if request.thresholds is not None:
            simulated_policy = simulated_policy.with_thresholds(request.thresholds)

        baseline_engine = baseline_policy.build_rule_engine()
        simulated_engine = simulated_policy.build_rule_engine()
        baseline_decision = baseline_policy.build_decision_engine()
        simulated_decision = simulated_policy.build_decision_engine()

        rows = await self._repo.get_recent_join_cases(limit=request.sample_size)
        baseline_counts = _empty_counts()
        simulated_counts = _empty_counts()
        for join_request, telegram_user in rows:
            features = self._feature_extractor.extract(telegram_user)
            baseline_score = baseline_engine.evaluate(features).rule_score
            simulated_score = simulated_engine.evaluate(features).rule_score
            baseline_decision_value = baseline_decision.decide(baseline_score)
            simulated_decision_value = simulated_decision.decide(simulated_score)
            baseline_counts[baseline_decision_value.value] += 1
            simulated_counts[simulated_decision_value.value] += 1

        baseline_delta = _to_delta(baseline_counts)
        simulated_delta = _to_delta(simulated_counts)
        return SimulationResult(
            sample_size=len(rows),
            baseline=baseline_delta,
            simulated=simulated_delta,
            delta=SimulationDecisionDelta(
                approved=simulated_delta.approved - baseline_delta.approved,
                rejected=simulated_delta.rejected - baseline_delta.rejected,
                manual_review=simulated_delta.manual_review - baseline_delta.manual_review,
            ),
        )


def _empty_counts() -> dict[str, int]:
    return {
        AnalysisDecision.APPROVED.value: 0,
        AnalysisDecision.REJECTED.value: 0,
        AnalysisDecision.MANUAL_REVIEW.value: 0,
    }


def _to_delta(counts: dict[str, int]) -> SimulationDecisionDelta:
    return SimulationDecisionDelta(
        approved=counts[AnalysisDecision.APPROVED.value],
        rejected=counts[AnalysisDecision.REJECTED.value],
        manual_review=counts[AnalysisDecision.MANUAL_REVIEW.value],
    )
