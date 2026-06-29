import time
from datetime import UTC, datetime

from app.ai.provider import AIProvider
from app.ai.result import AIAnalysisResult
from app.models.enums import AnalysisDecision
from app.risk.enums import RiskLevel
from app.risk.profile import RiskProfile

MOCK_MODEL = "mock-v1"

RISK_LEVEL_BASE: dict[RiskLevel, tuple[int, AnalysisDecision, float]] = {
    RiskLevel.LOW: (12, AnalysisDecision.APPROVED, 0.82),
    RiskLevel.MEDIUM: (52, AnalysisDecision.MANUAL_REVIEW, 0.71),
    RiskLevel.HIGH: (88, AnalysisDecision.REJECTED, 0.86),
}

MOCK_REASONS: dict[RiskLevel, str] = {
    RiskLevel.LOW: "Профиль имеет низкий уровень риска по сигналам.",
    RiskLevel.MEDIUM: "Профиль содержит умеренные признаки риска, требуется проверка.",
    RiskLevel.HIGH: "Профиль содержит множественные признаки высокого риска.",
}


class MockAIProvider(AIProvider):
    """Deterministic AI provider for tests and fallback scenarios."""

    @property
    def name(self) -> str:
        return "mock"

    def analyze(self, risk_profile: RiskProfile) -> AIAnalysisResult:
        started = time.perf_counter()
        base_score, decision, confidence = RISK_LEVEL_BASE[risk_profile.risk_level]
        signal_adjustment = min(len(risk_profile.signals) * 4, 20)
        ai_score = min(100, base_score + signal_adjustment)

        if risk_profile.risk_level == RiskLevel.LOW:
            ai_score = max(0, ai_score - signal_adjustment // 2)

        reason = MOCK_REASONS[risk_profile.risk_level]
        if risk_profile.main_reason:
            reason = f"{reason} {risk_profile.main_reason}"

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        prompt_tokens = 120 + len(risk_profile.signals) * 8
        completion_tokens = 45

        return AIAnalysisResult(
            ai_score=ai_score,
            confidence=round(min(confidence + len(risk_profile.signals) * 0.01, 0.99), 2),
            decision=decision,
            reason=reason,
            provider=self.name,
            response_time_ms=max(elapsed_ms, 1),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=MOCK_MODEL,
            created_at=datetime.now(UTC),
        )
