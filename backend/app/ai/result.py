from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from app.ai.enums import AIServiceStatus
from app.models.enums import AnalysisDecision


@dataclass(slots=True)
class AIAnalysisResult:
    ai_score: int
    confidence: float
    decision: AnalysisDecision
    reason: str
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
