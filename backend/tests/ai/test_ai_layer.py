import time
from datetime import UTC, datetime

import pytest

from app.ai.exceptions import AIProviderError, AITimeoutError
from app.ai.mock_provider import MockAIProvider
from app.ai.prompt_builder import PromptBuilder
from app.ai.provider import AIProvider
from app.ai.result import AIAnalysisResult
from app.ai.schemas import StructuredAnalysisOutput, structured_output_json_schema
from app.ai.service import AIService
from app.ai.enums import AIServiceStatus
from app.features import FeatureExtractor
from app.models.enums import AnalysisDecision
from app.models.telegram_user import TelegramUser
from app.risk import RiskLevel, RiskProfile, RiskProfileBuilder
from app.rules.engine import RuleEngine


def make_user(**kwargs: object) -> TelegramUser:
    defaults = {
        "telegram_id": 10001,
        "username": "normal_user",
        "first_name": "Ivan",
        "last_name": "Petrov",
        "language_code": "ru",
        "is_premium": False,
        "has_photo": True,
    }
    defaults.update(kwargs)
    return TelegramUser(**defaults)  # type: ignore[arg-type]


def build_risk_profile(**user_kwargs: object) -> RiskProfile:
    features = FeatureExtractor().extract(make_user(**user_kwargs))
    rule_result = RuleEngine().evaluate(features)
    return RiskProfileBuilder().build(features, rule_result)


class FailingProvider(AIProvider):
    def __init__(self, name: str = "failing", message: str = "provider failed") -> None:
        self._name = name
        self._message = message
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    def analyze(self, risk_profile: RiskProfile) -> AIAnalysisResult:
        self.calls += 1
        raise AIProviderError(self._message)


class SlowProvider(AIProvider):
    def __init__(self, delay_seconds: float) -> None:
        self._delay = delay_seconds

    @property
    def name(self) -> str:
        return "slow"

    def analyze(self, risk_profile: RiskProfile) -> AIAnalysisResult:
        time.sleep(self._delay)
        return MockAIProvider().analyze(risk_profile)


class CountingMockProvider(MockAIProvider):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def analyze(self, risk_profile: RiskProfile) -> AIAnalysisResult:
        self.calls += 1
        return super().analyze(risk_profile)


def test_mock_provider_low_risk() -> None:
    profile = build_risk_profile()
    result = MockAIProvider().analyze(profile)

    assert result.ai_score <= 30
    assert result.decision == AnalysisDecision.APPROVED
    assert 0.0 <= result.confidence <= 1.0
    assert result.provider == "mock"
    assert result.model == "mock-v1"
    assert result.total_tokens == result.prompt_tokens + result.completion_tokens
    assert result.created_at.tzinfo is not None


def test_mock_provider_medium_risk() -> None:
    profile = build_risk_profile(has_photo=False, username="user1234567")
    result = MockAIProvider().analyze(profile)

    assert profile.risk_level == RiskLevel.MEDIUM
    assert 40 <= result.ai_score <= 75
    assert result.decision == AnalysisDecision.MANUAL_REVIEW


def test_mock_provider_high_risk() -> None:
    profile = build_risk_profile(
        has_photo=False,
        username="crypto1234567",
        first_name="Crypto",
        last_name="Bonus",
        language_code=None,
    )
    result = MockAIProvider().analyze(profile)

    assert profile.risk_level == RiskLevel.HIGH
    assert result.ai_score >= 80
    assert result.decision == AnalysisDecision.REJECTED


def test_prompt_builder_contains_risk_fields_only() -> None:
    profile = build_risk_profile(username="secret_name", first_name="Secret", last_name="User")
    prompt = PromptBuilder().build(profile)

    assert profile.risk_level.value in prompt.user
    assert str(profile.confidence)[:3] in prompt.user or f"{profile.confidence:.2f}" in prompt.user
    assert profile.summary in prompt.user
    assert "Rule score:" in prompt.user
    assert "Trust score:" in prompt.user
    assert "History:" in prompt.user
    assert "secret_name" not in prompt.user.lower()
    assert "secret" not in prompt.user.lower()
    assert "telegram_id" not in prompt.user.lower()
    assert "chat_id" not in prompt.user.lower()
    assert prompt.system


def test_structured_output_schema_has_required_fields() -> None:
    schema = structured_output_json_schema()
    assert "risk_score" in schema["properties"]
    assert "decision" in schema["properties"]
    assert "recommended_action" in schema["properties"]


def test_ai_service_skips_approved_and_rejected() -> None:
    profile = build_risk_profile()
    mock = CountingMockProvider()
    service = AIService(provider=mock, fallback_provider=mock)

    approved = service.analyze(AnalysisDecision.APPROVED, profile)
    rejected = service.analyze(AnalysisDecision.REJECTED, profile)

    assert approved.status == AIServiceStatus.SKIPPED
    assert approved.analysis is None
    assert rejected.status == AIServiceStatus.SKIPPED
    assert mock.calls == 0


def test_ai_service_calls_provider_for_manual_review() -> None:
    profile = build_risk_profile(has_photo=False, username="user1234567")
    mock = CountingMockProvider()
    service = AIService(provider=mock, fallback_provider=mock, timeout=5.0)

    result = service.analyze(AnalysisDecision.MANUAL_REVIEW, profile)

    assert result.status == AIServiceStatus.SUCCESS
    assert result.analysis is not None
    assert result.analysis.decision == AnalysisDecision.MANUAL_REVIEW
    assert mock.calls == 1


def test_ai_service_retries_primary_before_fallback() -> None:
    profile = build_risk_profile(has_photo=False, username="user1234567")
    failing = FailingProvider()
    fallback = CountingMockProvider()
    service = AIService(
        provider=failing,
        fallback_provider=fallback,
        max_retries=2,
        timeout=5.0,
    )

    result = service.analyze(AnalysisDecision.MANUAL_REVIEW, profile)

    assert failing.calls == 2
    assert fallback.calls == 1
    assert result.status == AIServiceStatus.FALLBACK
    assert result.analysis is not None
    assert result.analysis.provider == "mock"


def test_ai_service_returns_unavailable_when_all_providers_fail() -> None:
    profile = build_risk_profile(has_photo=False, username="user1234567")
    service = AIService(
        provider=FailingProvider("primary"),
        fallback_provider=FailingProvider("fallback"),
        max_retries=2,
        timeout=5.0,
    )

    result = service.analyze(AnalysisDecision.MANUAL_REVIEW, profile)

    assert result.status == AIServiceStatus.UNAVAILABLE
    assert result.analysis is None
    assert result.error_message


def test_ai_service_timeout_triggers_fallback() -> None:
    profile = build_risk_profile(has_photo=False, username="user1234567")
    fallback = CountingMockProvider()
    service = AIService(
        provider=SlowProvider(delay_seconds=0.3),
        fallback_provider=fallback,
        max_retries=1,
        timeout=0.05,
    )

    result = service.analyze(AnalysisDecision.MANUAL_REVIEW, profile)

    assert result.status == AIServiceStatus.FALLBACK
    assert fallback.calls == 1


def test_integration_mock_provider_through_ai_service() -> None:
    profile = build_risk_profile(
        has_photo=False,
        username="user1234567",
        language_code=None,
    )
    service = AIService(
        provider=MockAIProvider(),
        fallback_provider=MockAIProvider(),
        timeout=5.0,
    )

    result = service.analyze(AnalysisDecision.MANUAL_REVIEW, profile)

    assert profile.risk_level == RiskLevel.MEDIUM
    assert result.status == AIServiceStatus.SUCCESS
    assert result.analysis is not None
    assert isinstance(result.analysis, AIAnalysisResult)
    assert result.analysis.ai_score >= 0
    assert result.analysis.reason
