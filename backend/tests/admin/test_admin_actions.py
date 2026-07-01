import json
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.ai_analysis import AIAnalysis
from app.models.audit_log import AuditLog
from app.models.blacklist import Blacklist
from app.models.enums import AnalysisDecision, JoinRequestStatus
from app.models.join_request import JoinRequest
from app.models.manual_review import AdminAction
from app.models.telegram_bot import TelegramBot
from app.models.telegram_channel import TelegramChannel
from app.models.telegram_user import TelegramUser
from app.models.whitelist import Whitelist
from app.repositories.deps import (
    get_ai_analysis_repository,
    get_ai_feedback_repository,
    get_audit_log_repository,
    get_join_request_repository,
    get_manual_review_repository,
    get_telegram_bot_repository,
    get_telegram_channel_repository,
    get_telegram_user_repository,
    get_user_repository,
)
from app.services.admin_dashboard import AdminDashboardService
from app.services.admin_join_request_action import AdminJoinRequestActionService
from tests.conftest import make_user


async def seed_action_context(
    session: AsyncSession,
    *,
    suffix: str,
    status: JoinRequestStatus = JoinRequestStatus.MANUAL_REVIEW,
    telegram_id: int = 920001,
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
            bot_token="test-token",
            bot_username=f"bot_{suffix}",
        )
    )
    channel = await channel_repo.create(
        TelegramChannel(
            owner_id=owner.id,
            bot_id=bot.id,
            telegram_chat_id=-1009200000 - abs(hash(suffix)) % 100000,
            title=f"Channel {suffix}",
            is_active=True,
        )
    )
    telegram_user = await telegram_user_repo.create(
        TelegramUser(
            telegram_id=telegram_id,
            username=f"user_{suffix}",
            first_name="Action",
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
            explanation=json.dumps({"ai_status": "FALLBACK"}, ensure_ascii=False),
        )
    )
    return join_request


def make_mock_bot_factory(mock_bot: AsyncMock):
    async def factory(_token: str) -> AsyncMock:
        return mock_bot

    return factory


@pytest.mark.asyncio
async def test_admin_approve_action_success(session: AsyncSession) -> None:
    join_request = await seed_action_context(session, suffix="ap1")
    mock_bot = AsyncMock()
    service = AdminJoinRequestActionService(session, bot_factory=make_mock_bot_factory(mock_bot))

    result = await service.approve(join_request.id)

    assert result.success is True
    assert "одобрен" in result.message.lower()
    mock_bot.approve_chat_join_request.assert_awaited_once()

    updated = await get_join_request_repository(session).get_by_id(join_request.id)
    assert updated is not None
    assert updated.status == JoinRequestStatus.APPROVED

    reviews = await get_manual_review_repository(session).list_by_join_request_id(join_request.id)
    assert len(reviews) == 1
    assert reviews[0].admin_action == AdminAction.APPROVE


@pytest.mark.asyncio
async def test_admin_reject_action_success(session: AsyncSession) -> None:
    join_request = await seed_action_context(session, suffix="rj1")
    mock_bot = AsyncMock()
    service = AdminJoinRequestActionService(session, bot_factory=make_mock_bot_factory(mock_bot))

    result = await service.reject(join_request.id)

    assert result.success is True
    mock_bot.decline_chat_join_request.assert_awaited_once()

    updated = await get_join_request_repository(session).get_by_id(join_request.id)
    assert updated is not None
    assert updated.status == JoinRequestStatus.REJECTED


@pytest.mark.asyncio
async def test_admin_approve_telegram_api_error(session: AsyncSession) -> None:
    join_request = await seed_action_context(session, suffix="te1")
    mock_bot = AsyncMock()
    mock_bot.approve_chat_join_request.side_effect = RuntimeError("Telegram unavailable")
    service = AdminJoinRequestActionService(session, bot_factory=make_mock_bot_factory(mock_bot))

    result = await service.approve(join_request.id)

    assert result.success is False
    assert result.error is not None

    updated = await get_join_request_repository(session).get_by_id(join_request.id)
    assert updated is not None
    assert updated.status == JoinRequestStatus.MANUAL_REVIEW

    audit_logs = await get_audit_log_repository(session).get_all(limit=10)
    assert any(log.action == "approve_error" for log in audit_logs)


@pytest.mark.asyncio
async def test_admin_whitelist_action(session: AsyncSession) -> None:
    join_request = await seed_action_context(session, suffix="wl1")
    mock_bot = AsyncMock()
    service = AdminJoinRequestActionService(session, bot_factory=make_mock_bot_factory(mock_bot))

    result = await service.whitelist(join_request.id)

    assert result.success is True
    from app.repositories.deps import get_whitelist_repository

    assert await get_whitelist_repository(session).exists_by_telegram_user_id(
        join_request.telegram_user_id
    )

    updated = await get_join_request_repository(session).get_by_id(join_request.id)
    assert updated is not None
    assert updated.status == JoinRequestStatus.APPROVED


@pytest.mark.asyncio
async def test_admin_blacklist_action(session: AsyncSession) -> None:
    join_request = await seed_action_context(session, suffix="bl1")
    mock_bot = AsyncMock()
    service = AdminJoinRequestActionService(session, bot_factory=make_mock_bot_factory(mock_bot))

    result = await service.blacklist(join_request.id)

    assert result.success is True
    from app.repositories.deps import get_blacklist_repository

    assert await get_blacklist_repository(session).exists_by_telegram_user_id(
        join_request.telegram_user_id
    )

    updated = await get_join_request_repository(session).get_by_id(join_request.id)
    assert updated is not None
    assert updated.status == JoinRequestStatus.REJECTED


@pytest.mark.asyncio
async def test_admin_action_creates_ai_feedback(session: AsyncSession) -> None:
    join_request = await seed_action_context(session, suffix="fb1")
    mock_bot = AsyncMock()
    service = AdminJoinRequestActionService(session, bot_factory=make_mock_bot_factory(mock_bot))

    await service.approve(join_request.id)

    feedbacks = await get_ai_feedback_repository(session).list_by_join_request_id(join_request.id)
    assert len(feedbacks) == 1
    assert feedbacks[0].ai_decision == AnalysisDecision.MANUAL_REVIEW
    assert feedbacks[0].human_decision == AnalysisDecision.APPROVED
    assert feedbacks[0].was_ai_correct is False


@pytest.mark.asyncio
async def test_detail_actions_disabled_for_final_status(session: AsyncSession) -> None:
    join_request = await seed_action_context(
        session,
        suffix="ds1",
        status=JoinRequestStatus.APPROVED,
    )
    dashboard = AdminDashboardService(session)
    detail = await dashboard.get_join_request_detail(join_request.id)

    assert detail is not None
    assert detail.actions_disabled is True
    assert detail.whitelist_disabled is False
    assert detail.blacklist_disabled is False


@pytest.mark.asyncio
async def test_whitelist_after_approve_adds_to_whitelist(session: AsyncSession) -> None:
    join_request = await seed_action_context(session, suffix="wla1")
    mock_bot = AsyncMock()
    service = AdminJoinRequestActionService(session, bot_factory=make_mock_bot_factory(mock_bot))

    approve_result = await service.approve(join_request.id)
    assert approve_result.success is True

    whitelist_result = await service.whitelist(join_request.id)
    assert whitelist_result.success is True

    from app.repositories.deps import get_whitelist_repository

    assert await get_whitelist_repository(session).exists_by_telegram_user_id(
        join_request.telegram_user_id
    )
    mock_bot.approve_chat_join_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_api_approve_endpoint(session: AsyncSession) -> None:
    join_request = await seed_action_context(session, suffix="api-ap1")

    async def override_get_db_session():
        yield session

    from app.database.session import get_db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    mock_bot = AsyncMock()

    async def override_action_service():
        return AdminJoinRequestActionService(session, bot_factory=make_mock_bot_factory(mock_bot))

    from app.api.v1 import admin as admin_api

    app.dependency_overrides[admin_api.get_action_service] = override_action_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/api/v1/admin/join-requests/{join_request.id}/approve")
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True

    app.dependency_overrides.clear()
