import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.ai.enums import AIServiceStatus
from app.ai.exceptions import AIProviderError, AITimeoutError
from app.ai.mock_provider import MockAIProvider
from app.ai.openrouter_provider import OpenRouterProvider
from app.ai.router import AIRouter
from app.ai.schemas import StructuredAnalysisOutput, structured_output_json_schema
from app.ai.service import AIService
from app.config import get_settings
from app.models.enums import AnalysisDecision
from app.repositories.deps import get_ai_usage_repository
from tests.ai.test_ai_layer import (
    CountingMockProvider,
    FailingProvider,
    SlowProvider,
    build_risk_profile,
)


def _valid_ai_json(**overrides: object) -> str:
    payload = {
        "risk_score": 48,
        "confidence": 0.72,
        "decision": "ManualReview",
        "reason": "Moderate risk profile with multiple signals.",
        "recommended_action": "ManualReview",
        "signals": ["no_photo"],
    }
    payload.update(overrides)
    return json.dumps(payload)


def _mock_http_response(content: str, *, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 60,
            "total_tokens": 210,
        },
    }
    return response


def _mock_http_client(response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.post.return_value = response
    return client


def test_structured_output_schema_uses_risk_score_alias() -> None:
    schema = structured_output_json_schema()
    assert "risk_score" in schema["properties"]
    assert "recommended_action" in schema["properties"]
    assert "signals" in schema["properties"]


def test_structured_output_accepts_risk_score_field() -> None:
    parsed = StructuredAnalysisOutput.model_validate_json(_valid_ai_json())
    assert parsed.ai_score == 48
    assert parsed.recommended_action == "ManualReview"


def test_prompt_builder_includes_extended_fields_without_pii() -> None:
    from app.ai.prompt_builder import PromptBuilder
    from app.risk.enums import RiskLevel
    from app.risk.profile import RiskProfile

    profile = RiskProfile(
        risk_level=RiskLevel.MEDIUM,
        confidence=0.71,
        main_reason="No photo",
        signals=["no_photo"],
        summary="Test summary",
        trust_score=55.0,
        rule_score=45.0,
        history=["MANUAL_APPROVED: 50 -> 55"],
    )
    prompt = PromptBuilder().build(profile)

    assert "Rule score: 45" in prompt.user
    assert "Trust score: 55" in prompt.user
    assert "MANUAL_APPROVED: 50 -> 55" in prompt.user
    assert "telegram_id" not in prompt.user.lower()
    assert "username" not in prompt.user.lower()


@patch("app.ai.openrouter_provider.httpx.Client")
def test_openrouter_provider_parses_json_object_response(mock_client_cls: MagicMock) -> None:
    mock_client_cls.return_value = _mock_http_client(_mock_http_response(_valid_ai_json()))
    provider = OpenRouterProvider(api_key="test-key", model="openai/gpt-4.1", timeout=5.0)

    result = provider.analyze(build_risk_profile(has_photo=False, username="user1234567"))

    assert result.provider == "openrouter"
    assert result.model == "openai/gpt-4.1"
    assert result.decision == AnalysisDecision.MANUAL_REVIEW
    assert result.ai_score == 48
    assert result.prompt_tokens == 150
    assert result.completion_tokens == 60
    mock_client_cls.return_value.post.assert_called_once()
    payload = mock_client_cls.return_value.post.call_args.kwargs["json"]
    assert payload["response_format"] == {"type": "json_object"}
    system_message = payload["messages"][0]["content"]
    assert "valid JSON object" in system_message
    assert "Do not use markdown" in system_message
    headers = mock_client_cls.return_value.post.call_args.kwargs["headers"]
    assert headers["Authorization"].startswith("Bearer ")
    assert headers["Content-Type"] == "application/json"


@patch("app.ai.openrouter_provider.httpx.Client")
def test_openrouter_provider_invalid_json_triggers_fallback_via_service(
    mock_client_cls: MagicMock,
) -> None:
    mock_client_cls.return_value = _mock_http_client(
        _mock_http_response("not-valid-json"),
    )
    provider = OpenRouterProvider(api_key="test-key", timeout=5.0)
    fallback = CountingMockProvider()
    service = AIService(
        provider=provider,
        fallback_provider=fallback,
        max_retries=1,
        timeout=5.0,
    )

    result = service.analyze(
        AnalysisDecision.MANUAL_REVIEW,
        build_risk_profile(has_photo=False, username="user1234567"),
    )

    assert result.status == AIServiceStatus.FALLBACK
    assert result.analysis is not None
    assert result.analysis.provider == "mock"
    assert fallback.calls == 1


@patch("app.ai.openrouter_provider.httpx.Client")
def test_openrouter_provider_http_400_logged_without_api_key(
    mock_client_cls: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    secret_key = "sk-or-v1-secret-test-key"
    response = MagicMock()
    response.status_code = 400
    response.text = f"invalid key {secret_key}"
    response.json.return_value = {
        "error": {"message": f"Provider error with {secret_key}"},
    }
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "error",
        request=MagicMock(),
        response=response,
    )
    mock_client_cls.return_value = _mock_http_client(response)

    provider = OpenRouterProvider(api_key=secret_key, timeout=5.0)
    with caplog.at_level(logging.ERROR, logger="app.ai.openrouter_provider"):
        with pytest.raises(AIProviderError, match="OpenRouter HTTP error: 400"):
            provider.analyze(build_risk_profile(has_photo=False, username="user1234567"))

    log_text = caplog.text
    assert secret_key not in log_text
    assert "OpenRouter HTTP error status=400" in log_text


@patch("app.ai.openrouter_provider.httpx.Client")
def test_openrouter_provider_http_error(mock_client_cls: MagicMock) -> None:
    response = MagicMock()
    response.status_code = 503
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "error",
        request=MagicMock(),
        response=response,
    )
    mock_client_cls.return_value = _mock_http_client(response)

    provider = OpenRouterProvider(api_key="test-key", timeout=5.0)
    with pytest.raises(AIProviderError):
        provider.analyze(build_risk_profile(has_photo=False, username="user1234567"))


@patch("app.ai.openrouter_provider.httpx.Client")
def test_openrouter_provider_timeout(mock_client_cls: MagicMock) -> None:
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.post.side_effect = httpx.TimeoutException("timeout")
    mock_client_cls.return_value = client

    provider = OpenRouterProvider(api_key="test-key", timeout=1.0)
    with pytest.raises(AITimeoutError):
        provider.analyze(build_risk_profile(has_photo=False, username="user1234567"))


def test_ai_router_selects_mock_without_openrouter_key(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    provider = AIRouter.create_primary_provider()
    assert provider.name == "mock"


def test_ai_router_selects_openrouter_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-key")

    provider = AIRouter.create_primary_provider()
    assert provider.name == "openrouter"


def test_ai_service_openrouter_fallback_to_mock() -> None:
    profile = build_risk_profile(has_photo=False, username="user1234567")
    failing = FailingProvider(name="openrouter")
    fallback = CountingMockProvider()
    service = AIService(provider=failing, fallback_provider=fallback, max_retries=2, timeout=5.0)

    result = service.analyze(AnalysisDecision.MANUAL_REVIEW, profile)

    assert failing.calls == 2
    assert fallback.calls == 1
    assert result.status == AIServiceStatus.FALLBACK


def test_ai_service_openrouter_timeout_fallback() -> None:
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


@pytest.mark.asyncio
async def test_ai_usage_persisted_after_join_pipeline_ai_call(session) -> None:
    from unittest.mock import AsyncMock, MagicMock

    from app.features.feature_set import FeatureSet
    from app.rules.engine import RuleEngine, RuleEngineResult
    from app.services.join_request_processing import JoinRequestProcessingService
    from tests.services.test_join_request_processing import (
        create_registered_channel,
        make_ai_service,
        make_join_request_event,
    )

    class ManualReviewRuleEngine(RuleEngine):
        def evaluate(self, features: FeatureSet) -> RuleEngineResult:
            return RuleEngineResult(rule_score=45, triggered_rules=[])

    chat_id = -100700020
    await create_registered_channel(session, chat_id)
    mock_bot = AsyncMock()
    mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=0)

    service = JoinRequestProcessingService(
        session,
        mock_bot,
        rule_engine=ManualReviewRuleEngine(),
        ai_service=make_ai_service(),
    )
    await service.process(make_join_request_event(chat_id=chat_id, user_id=900020))

    usage_repo = get_ai_usage_repository(session)
    stats = await usage_repo.get_statistics()
    assert stats["total_requests"] >= 1
    assert stats["total_tokens"] > 0
