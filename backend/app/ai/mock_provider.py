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

MOCK_EXPLAINABLE: dict[RiskLevel, dict[str, object]] = {
    RiskLevel.LOW: {
        "reason": "Профиль выглядит обычным, явных признаков риска не обнаружено.",
        "recommended_action": "Одобрить заявку.",
        "positive_signals": ["есть фото профиля", "есть username", "нет подозрительных слов"],
        "negative_signals": [],
        "short_summary": "Низкий риск.",
    },
    RiskLevel.MEDIUM: {
        "reason": "Пользователь выглядит обычным, но отсутствует фото профиля и/или username.",
        "recommended_action": "Оставить на ручную проверку.",
        "positive_signals": ["нет подозрительных слов", "нет крипто-признаков"],
        "negative_signals": ["нет фото", "нет username"],
        "short_summary": "Низкий–средний риск.",
    },
    RiskLevel.HIGH: {
        "reason": "Профиль содержит множественные признаки высокого риска.",
        "recommended_action": "Отклонить заявку.",
        "positive_signals": [],
        "negative_signals": [
            "нет фото",
            "подозрительный username",
            "крипто-признаки",
            "множественные сигналы риска",
        ],
        "short_summary": "Высокий риск.",
    },
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

        explainable = MOCK_EXPLAINABLE[risk_profile.risk_level]
        reason = str(explainable["reason"])
        if risk_profile.main_reason:
            reason = f"{reason} {risk_profile.main_reason}"

        positive_signals = list(explainable["positive_signals"])  # type: ignore[arg-type]
        negative_signals = list(explainable["negative_signals"])  # type: ignore[arg-type]
        for signal in risk_profile.signals:
            label = signal.replace("_", " ")
            if signal.startswith("no_") or "suspicious" in signal or "crypto" in signal:
                if label not in negative_signals:
                    negative_signals.append(label)
            elif label not in positive_signals:
                positive_signals.append(label)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        prompt_tokens = 120 + len(risk_profile.signals) * 8
        completion_tokens = 45

        return AIAnalysisResult(
            ai_score=ai_score,
            confidence=round(min(confidence + len(risk_profile.signals) * 0.01, 0.99), 2),
            decision=decision,
            reason=reason,
            recommended_action=str(explainable["recommended_action"]),
            positive_signals=positive_signals,
            negative_signals=negative_signals,
            short_summary=str(explainable["short_summary"]),
            provider=self.name,
            response_time_ms=max(elapsed_ms, 1),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=MOCK_MODEL,
            created_at=datetime.now(UTC),
        )
