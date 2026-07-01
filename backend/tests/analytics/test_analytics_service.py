import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.ai_analysis import AIAnalysis
from app.models.ai_feedback import AIFeedback
from app.models.ai_usage import AIUsage
from app.models.enums import AnalysisDecision, JoinRequestStatus
from app.models.join_request import JoinRequest
from app.models.telegram_bot import TelegramBot
from app.models.telegram_channel import TelegramChannel
from app.models.telegram_user import TelegramUser
from app.repositories.deps import (
    get_ai_analysis_repository,
    get_ai_feedback_repository,
    get_ai_usage_repository,
    get_join_request_repository,
    get_telegram_bot_repository,
    get_telegram_channel_repository,
    get_telegram_user_repository,
    get_user_repository,
)
from app.services.analytics import AnalyticsService
from tests.conftest import make_user


async def seed_analytics_data(session: AsyncSession, *, suffix: str) -> JoinRequest:
    user_repo = get_user_repository(session)
    bot_repo = get_telegram_bot_repository(session)
    channel_repo = get_telegram_channel_repository(session)
    telegram_user_repo = get_telegram_user_repository(session)
    join_request_repo = get_join_request_repository(session)
    analysis_repo = get_ai_analysis_repository(session)
    feedback_repo = get_ai_feedback_repository(session)
    usage_repo = get_ai_usage_repository(session)

    owner = await user_repo.create(make_user(f"owner-{suffix}"))
    bot = await bot_repo.create(
        TelegramBot(owner_id=owner.id, bot_token="token", bot_username=f"bot_{suffix}")
    )
    channel = await channel_repo.create(
        TelegramChannel(
            owner_id=owner.id,
            bot_id=bot.id,
            telegram_chat_id=-1008000000 - abs(hash(suffix)) % 100000,
            title=f"Channel {suffix}",
            is_active=True,
        )
    )
    telegram_user = await telegram_user_repo.create(
        TelegramUser(
            telegram_id=920000 + abs(hash(suffix)) % 10000,
            username=f"user_{suffix}",
            first_name="Test",
            last_name="User",
            language_code="ru",
            is_premium=True,
            has_photo=True,
        )
    )
    join_request = await join_request_repo.create(
        JoinRequest(
            channel_id=channel.id,
            telegram_user_id=telegram_user.id,
            status=JoinRequestStatus.APPROVED,
        )
    )
    explanation = json.dumps(
        {
            "triggered_rules": [{"rule": "NoPhotoRule", "score": 20}],
            "risk_profile": {"risk_level": "MEDIUM", "confidence": 0.7, "signals": []},
            "ai_result": {
                "provider": "openrouter",
                "model": "openai/gpt-4o-mini",
                "confidence": 0.82,
                "decision": "ManualReview",
                "response_time_ms": 2300,
            },
            "ai_status": "SUCCESS",
        },
        ensure_ascii=False,
    )
    await analysis_repo.create(
        AIAnalysis(
            join_request_id=join_request.id,
            rule_score=20.0,
            ai_score=48.0,
            final_score=34.0,
            decision=AnalysisDecision.MANUAL_REVIEW,
            explanation=explanation,
        )
    )
    await feedback_repo.create(
        AIFeedback(
            join_request_id=join_request.id,
            rule_score=20.0,
            ai_score=48.0,
            ai_decision=AnalysisDecision.MANUAL_REVIEW,
            human_decision=AnalysisDecision.APPROVED,
            was_ai_correct=False,
        )
    )
    await usage_repo.create(
        AIUsage(
            provider="openrouter",
            model="openai/gpt-4o-mini",
            prompt_tokens=150,
            completion_tokens=60,
            total_tokens=210,
            estimated_cost=0.00008,
            latency_ms=2300,
        )
    )
    return join_request


@pytest.mark.asyncio
async def test_analytics_service_accuracy(session: AsyncSession) -> None:
    await seed_analytics_data(session, suffix="acc1")
    service = AnalyticsService(session)

    accuracy = await service.get_accuracy()

    assert accuracy.total_decisions >= 1
    assert accuracy.mismatched >= 1
    assert accuracy.false_approve == 0
    assert accuracy.accuracy_percent is not None


@pytest.mark.asyncio
async def test_analytics_service_rule_effectiveness(session: AsyncSession) -> None:
    await seed_analytics_data(session, suffix="rule1")
    service = AnalyticsService(session)

    rules = await service.get_rule_effectiveness()

    assert any(item.rule_name == "NoPhotoRule" for item in rules)
    no_photo = next(item for item in rules if item.rule_name == "NoPhotoRule")
    assert no_photo.triggered_count >= 1
    assert no_photo.ai_agreed_count >= 1


@pytest.mark.asyncio
async def test_analytics_service_provider_statistics(session: AsyncSession) -> None:
    await seed_analytics_data(session, suffix="prov1")
    service = AnalyticsService(session)

    providers = await service.get_provider_statistics()

    assert any(item.provider == "openrouter" for item in providers)
    openrouter = next(item for item in providers if item.provider == "openrouter")
    assert openrouter.requests >= 1
    assert openrouter.avg_latency_ms > 0


@pytest.mark.asyncio
async def test_analytics_service_decision_comparison(session: AsyncSession) -> None:
    join_request = await seed_analytics_data(session, suffix="cmp1")
    service = AnalyticsService(session)

    comparison = await service.build_decision_comparison(join_request.id)

    assert comparison is not None
    assert comparison.has_override is True
    assert comparison.verdict == "AI ошибся"


@pytest.mark.asyncio
async def test_analytics_api_endpoints(session: AsyncSession, admin_client: AsyncClient) -> None:
    await seed_analytics_data(session, suffix="api1")
    overview = await admin_client.get("/api/v1/admin/analytics")
    assert overview.status_code == 200
    payload = overview.json()
    assert payload["accuracy"]["total_decisions"] >= 1
    assert "providers" in payload

    accuracy = await admin_client.get("/api/v1/admin/analytics/accuracy")
    assert accuracy.status_code == 200

    rules = await admin_client.get("/api/v1/admin/analytics/rules")
    assert rules.status_code == 200
    assert isinstance(rules.json(), list)

    providers = await admin_client.get("/api/v1/admin/analytics/providers")
    assert providers.status_code == 200

    timeline = await admin_client.get("/api/v1/admin/analytics/timeline?days=30")
    assert timeline.status_code == 200


@pytest.mark.asyncio
async def test_admin_analytics_page(session: AsyncSession, admin_client: AsyncClient) -> None:
    await seed_analytics_data(session, suffix="web1")
    response = await admin_client.get("/admin/analytics")
    assert response.status_code == 200
    assert "AI Analytics" in response.text
    assert "Rule Effectiveness" in response.text
