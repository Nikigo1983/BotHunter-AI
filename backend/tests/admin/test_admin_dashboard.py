import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.ai_analysis import AIAnalysis
from app.models.enums import AnalysisDecision, JoinRequestStatus
from app.models.join_request import JoinRequest
from app.models.telegram_bot import TelegramBot
from app.models.telegram_channel import TelegramChannel
from app.models.telegram_user import TelegramUser
from app.repositories.deps import (
    get_ai_analysis_repository,
    get_join_request_repository,
    get_reputation_repository,
    get_telegram_bot_repository,
    get_telegram_channel_repository,
    get_telegram_user_repository,
    get_user_repository,
)
from app.services.admin_dashboard import AdminDashboardService
from tests.conftest import make_user


async def seed_join_request(
    session: AsyncSession,
    *,
    suffix: str,
    status: JoinRequestStatus = JoinRequestStatus.MANUAL_REVIEW,
    telegram_id: int = 910001,
    username: str = "risk_user",
    channel_title: str = "Test Channel",
) -> JoinRequest:
    user_repo = get_user_repository(session)
    bot_repo = get_telegram_bot_repository(session)
    channel_repo = get_telegram_channel_repository(session)
    telegram_user_repo = get_telegram_user_repository(session)
    join_request_repo = get_join_request_repository(session)
    analysis_repo = get_ai_analysis_repository(session)

    owner = await user_repo.create(make_user(f"owner-{suffix}"))
    bot = await bot_repo.create(
        TelegramBot(
            owner_id=owner.id,
            bot_token="token",
            bot_username=f"bot_{suffix}",
        )
    )
    channel = await channel_repo.create(
        TelegramChannel(
            owner_id=owner.id,
            bot_id=bot.id,
            telegram_chat_id=-1009000000 - abs(hash(suffix)) % 100000,
            title=channel_title,
            is_active=True,
        )
    )
    telegram_user = await telegram_user_repo.create(
        TelegramUser(
            telegram_id=telegram_id,
            username=username,
            first_name="Join",
            last_name="User",
            language_code="ru",
            is_premium=False,
            has_photo=False,
        )
    )
    join_request = await join_request_repo.create(
        JoinRequest(
            channel_id=channel.id,
            telegram_user_id=telegram_user.id,
            status=status,
        )
    )
    await analysis_repo.create(
        AIAnalysis(
            join_request_id=join_request.id,
            rule_score=45.0,
            ai_score=52.0,
            final_score=48.5,
            decision=AnalysisDecision.MANUAL_REVIEW,
            explanation=json.dumps(
                {
                    "triggered_rules": [{"rule": "NoPhotoRule", "score": 20}],
                    "risk_profile": {
                        "risk_level": "MEDIUM",
                        "confidence": 0.71,
                        "signals": ["no_photo"],
                        "summary": "Test summary",
                        "main_reason": "No photo",
                    },
                    "ai_result": {
                        "ai_score": 52,
                        "decision": "ManualReview",
                        "confidence": 0.82,
                        "reason": "Пользователь выглядит обычным, но отсутствует фото профиля.",
                        "recommended_action": "Оставить на ручную проверку.",
                        "positive_signals": ["нет подозрительных слов"],
                        "negative_signals": ["нет фото"],
                        "short_summary": "Низкий–средний риск.",
                        "provider": "mock",
                    },
                    "ai_status": "SUCCESS",
                },
                ensure_ascii=False,
            ),
        )
    )
    return join_request


@pytest.mark.asyncio
async def test_admin_dashboard_service_list_and_statistics(session: AsyncSession) -> None:
    await seed_join_request(session, suffix="a1", status=JoinRequestStatus.APPROVED, telegram_id=910101)
    await seed_join_request(session, suffix="a2", status=JoinRequestStatus.MANUAL_REVIEW, telegram_id=910102)

    service = AdminDashboardService(session)
    result = await service.list_join_requests(status_filter="all", page=1)
    stats = await service.get_statistics()

    assert result.total >= 2
    assert len(result.items) >= 2
    assert stats.total >= 2
    assert stats.manual_review >= 1
    assert stats.approved >= 1
    assert stats.avg_trust_score is not None


@pytest.mark.asyncio
async def test_admin_dashboard_trust_score_on_list_and_detail(session: AsyncSession) -> None:
    join_request = await seed_join_request(session, suffix="trust1", telegram_id=910201)
    telegram_user = await get_telegram_user_repository(session).get_by_telegram_id(910201)
    assert telegram_user is not None
    reputation_repo = get_reputation_repository(session)
    reputation = await reputation_repo.get_or_create(telegram_user.id)
    reputation.reputation_score = 78.0
    await reputation_repo.update(reputation)

    service = AdminDashboardService(session)
    result = await service.list_join_requests(status_filter="all", search="910201")
    detail = await service.get_join_request_detail(join_request.id)

    assert result.items[0].trust_score == 78.0
    assert detail is not None
    assert detail.trust_score == 78.0


@pytest.mark.asyncio
async def test_admin_api_reputation_detail(session: AsyncSession, admin_client: AsyncClient) -> None:
    await seed_join_request(session, suffix="repapi", telegram_id=910301)
    telegram_user = await get_telegram_user_repository(session).get_by_telegram_id(910301)
    assert telegram_user is not None

    from app.reputation.enums import ReputationChangeReason
    from app.reputation.service import ReputationService

    reputation_service = ReputationService(session)
    await reputation_service.increase(
        telegram_user.id,
        reason=ReputationChangeReason.MANUAL_APPROVED,
    )

    response = await admin_client.get("/api/v1/admin/reputation/910301")
    assert response.status_code == 200
    payload = response.json()
    assert payload["current_score"] == 55.0
    assert len(payload["history"]) >= 1
    assert payload["trend"] in {"UP", "DOWN", "STABLE"}


@pytest.mark.asyncio
async def test_admin_web_dashboard_shows_trust(session: AsyncSession, admin_client: AsyncClient) -> None:
    await seed_join_request(session, suffix="webtrust", channel_title="Trust Channel", telegram_id=910401)
    telegram_user = await get_telegram_user_repository(session).get_by_telegram_id(910401)
    assert telegram_user is not None
    reputation_repo = get_reputation_repository(session)
    reputation = await reputation_repo.get_or_create(telegram_user.id)
    reputation.reputation_score = 82.0
    await reputation_repo.update(reputation)

    response = await admin_client.get("/admin")
    assert response.status_code == 200
    assert "Avg Trust" in response.text
    assert "82" in response.text


@pytest.mark.asyncio
async def test_admin_dashboard_service_search_by_telegram_id(session: AsyncSession) -> None:
    await seed_join_request(session, suffix="s1", telegram_id=777888999)

    service = AdminDashboardService(session)
    result = await service.list_join_requests(search="777888999")

    assert result.total == 1
    assert result.items[0].telegram_id == 777888999


@pytest.mark.asyncio
async def test_admin_dashboard_service_detail(session: AsyncSession) -> None:
    join_request = await seed_join_request(session, suffix="d1")

    service = AdminDashboardService(session)
    detail = await service.get_join_request_detail(join_request.id)

    assert detail is not None
    assert detail.user.username == "risk_user"
    assert detail.rules.rule_score == 45.0
    assert detail.risk_profile.risk_level == "MEDIUM"
    assert detail.ai.ai_status == "SUCCESS"
    assert detail.ai.explainable is not None
    assert detail.ai.explainable.reason
    assert detail.ai.explainable.positive_signals or detail.ai.explainable.negative_signals
    assert detail.ai.explainable.risk_level == "medium"
    assert detail.ai.explainable.risk_level_label == "Средний риск"
    assert "profile" in detail.feature_set



@pytest.mark.asyncio
async def test_admin_api_list_join_requests(session: AsyncSession, admin_client: AsyncClient) -> None:
    await seed_join_request(session, suffix="api1")
    response = await admin_client.get("/api/v1/admin/join-requests")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert len(payload["items"]) >= 1


@pytest.mark.asyncio
async def test_admin_api_get_join_request_detail(session: AsyncSession, admin_client: AsyncClient) -> None:
    join_request = await seed_join_request(session, suffix="api2")
    response = await admin_client.get(f"/api/v1/admin/join-requests/{join_request.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(join_request.id)
    assert payload["rules"]["rule_score"] == 45.0


@pytest.mark.asyncio
async def test_admin_api_statistics(session: AsyncSession, admin_client: AsyncClient) -> None:
    await seed_join_request(session, suffix="api3")
    response = await admin_client.get("/api/v1/admin/statistics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1


@pytest.mark.asyncio
async def test_admin_web_dashboard_page(session: AsyncSession, admin_client: AsyncClient) -> None:
    await seed_join_request(session, suffix="web1", channel_title="Dashboard Channel")
    response = await admin_client.get("/admin")
    assert response.status_code == 200
    assert "Dashboard Channel" in response.text
    assert "Join Requests" in response.text
