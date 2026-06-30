from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from app.ai.enums import AIServiceStatus
from app.ai.schemas import StructuredAnalysisOutput
from app.models.enums import AnalysisDecision

DECISION_MAP = {
    "Approved": AnalysisDecision.APPROVED,
    "ManualReview": AnalysisDecision.MANUAL_REVIEW,
    "Rejected": AnalysisDecision.REJECTED,
}


@dataclass(slots=True)
class AIAnalysisResult:
    ai_score: int
    confidence: float
    decision: AnalysisDecision
    reason: str
    recommended_action: str
    positive_signals: list[str]
    negative_signals: list[str]
    short_summary: str
    provider: str
    response_time_ms: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["decision"] = self.decision.value
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass(slots=True)
class AIServiceResult:
    status: AIServiceStatus
    analysis: AIAnalysisResult | None = None
    error_message: str | None = None


def build_analysis_result(
    parsed: StructuredAnalysisOutput,
    *,
    provider: str,
    model: str,
    response_time_ms: int,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> AIAnalysisResult:
    if parsed.decision not in DECISION_MAP:
        raise ValueError(f"Unknown decision value: {parsed.decision}")

    return AIAnalysisResult(
        ai_score=parsed.ai_score,
        confidence=round(parsed.confidence, 2),
        decision=DECISION_MAP[parsed.decision],
        reason=parsed.reason,
        recommended_action=parsed.recommended_action,
        positive_signals=list(parsed.positive_signals),
        negative_signals=list(parsed.negative_signals),
        short_summary=parsed.short_summary or parsed.reason[:200],
        provider=provider,
        response_time_ms=max(response_time_ms, 1),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model=model,
        created_at=datetime.now(UTC),
    )
