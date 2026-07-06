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
from app.repositories.channel_settings import ChannelSettingsRepository
from app.repositories.deps import (
    get_ai_analysis_repository,
    get_channel_repository,
    get_channel_settings_repository,
    get_join_request_repository,
    get_telegram_bot_repository,
    get_telegram_channel_repository,
    get_telegram_user_repository,
    get_user_repository,
)
from app.schemas.channel_management import ChannelSettingsUpdateRequest
from app.services.admin_channel import AdminChannelService
from tests.conftest import make_user


async def seed_channel(
    session: AsyncSession,
    *,
    suffix: str,
    is_active: bool = True,
    username: str | None = "mychannel",
) -> TelegramChannel:
    user_repo = get_user_repository(session)
    bot_repo = get_telegram_bot_repository(session)
    channel_repo = get_telegram_channel_repository(session)
    settings_repo = get_channel_settings_repository(session)
    telegram_user_repo = get_telegram_user_repository(session)
    join_request_repo = get_join_request_repository(session)
    analysis_repo = get_ai_analysis_repository(session)

    owner = await user_repo.create(make_user(f"owner-{suffix}"))
    bot = await bot_repo.create(
        TelegramBot(owner_id=owner.id, bot_token="token", bot_username=f"bot_{suffix}")
    )
    channel = await channel_repo.create(
        TelegramChannel(
            owner_id=owner.id,
            bot_id=bot.id,
            telegram_chat_id=-1007000000 - abs(hash(suffix)) % 100000,
            title=f"Channel {suffix}",
            username=username,
            is_active=is_active,
        )
    )
    await settings_repo.get_or_create(channel.id)

    telegram_user = await telegram_user_repo.create(
        TelegramUser(
            telegram_id=930000 + abs(hash(suffix)) % 10000,
            username=f"user_{suffix}",
            first_name="Test",
            last_name="User",
            language_code="ru",
            is_premium=False,
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
    await analysis_repo.create(
        AIAnalysis(
            join_request_id=join_request.id,
            rule_score=25.0,
            ai_score=40.0,
            final_score=32.5,
            decision=AnalysisDecision.APPROVED,
            explanation=json.dumps({"ai_status": "SUCCESS", "ai_result": {"provider": "mock"}}),
        )
    )
    return channel


@pytest.mark.asyncio
async def test_channel_settings_repository_get_or_create_defaults(session: AsyncSession) -> None:
    channel = await seed_channel(session, suffix="settings-defaults")
    repo = ChannelSettingsRepository(session)
    settings = await repo.get_or_create(channel.id)
    assert settings.ai_enabled is True
    assert settings.rule_auto_approve == 30
    assert settings.rule_auto_reject == 70
    assert settings.trust_auto_approve == 90
    assert settings.trust_auto_reject == 10


@pytest.mark.asyncio
async def test_channel_repository_set_active(session: AsyncSession) -> None:
    channel = await seed_channel(session, suffix="repo-active")
    repo = get_channel_repository(session)
    updated = await repo.set_active(channel.id, is_active=False)
    assert updated is not None
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_admin_channel_service_list_and_detail(session: AsyncSession) -> None:
    channel = await seed_channel(session, suffix="svc-list")
    service = AdminChannelService(session)

    items = await service.list_channels()
    assert any(item.id == channel.id for item in items)

    detail = await service.get_channel_detail(channel.id)
    assert detail is not None
    assert detail.title == channel.title
    assert detail.username == "mychannel"
    assert detail.total_requests == 1
    assert detail.approved == 1
    assert detail.settings.rule_auto_approve == 30
    assert len(detail.recent_requests) == 1


@pytest.mark.asyncio
async def test_admin_channel_service_update_settings_and_disable(session: AsyncSession) -> None:
    channel = await seed_channel(session, suffix="svc-update")
    service = AdminChannelService(session)

    updated = await service.update_channel(
        channel.id,
        ChannelSettingsUpdateRequest(
            ai_enabled=False,
            rule_auto_approve=25,
            rule_auto_reject=75,
            trust_auto_approve=85,
            trust_auto_reject=15,
            join_request_timeout_hours=48,
        ),
    )
    assert updated is not None
    assert updated.settings.ai_enabled is False
    assert updated.settings.rule_auto_approve == 25
    assert updated.settings.join_request_timeout_hours == 48

    disabled = await service.set_channel_active(channel.id, is_active=False)
    assert disabled is not None
    assert disabled.is_active is False

    enabled = await service.set_channel_active(channel.id, is_active=True)
    assert enabled is not None
    assert enabled.is_active is True


@pytest.mark.asyncio
async def test_admin_channel_service_statistics(session: AsyncSession) -> None:
    channel = await seed_channel(session, suffix="svc-stats")
    service = AdminChannelService(session)
    stats = await service.get_statistics(channel.id)
    assert stats is not None
    assert stats["total_requests"] == 1
    assert stats["approved"] == 1


@pytest.mark.asyncio
async def test_channels_api_endpoints(session: AsyncSession, admin_client: AsyncClient) -> None:
    channel = await seed_channel(session, suffix="api-ch")
    list_response = await admin_client.get("/api/v1/admin/channels")
    assert list_response.status_code == 200
    items = list_response.json()
    assert any(item["id"] == str(channel.id) for item in items)

    detail_response = await admin_client.get(f"/api/v1/admin/channels/{channel.id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["title"] == channel.title
    assert detail["statistics"]["approved"] == 1
    assert "settings" in detail
    assert "timeline" in detail

    stats_response = await admin_client.get(f"/api/v1/admin/channels/{channel.id}/statistics")
    assert stats_response.status_code == 200
    assert stats_response.json()["total_requests"] == 1

    patch_response = await admin_client.patch(
        f"/api/v1/admin/channels/{channel.id}",
        json={"ai_enabled": False, "is_active": False},
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["settings"]["ai_enabled"] is False
    assert patched["is_active"] is False

    invalid_patch = await admin_client.patch(
        f"/api/v1/admin/channels/{channel.id}",
        json={"rule_auto_approve": 80, "rule_auto_reject": 70},
    )
    assert invalid_patch.status_code == 422

    missing = await admin_client.get(f"/api/v1/admin/channels/{uuid.uuid4()}")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_channels_web_pages(session: AsyncSession, admin_client: AsyncClient, admin_csrf: str) -> None:
    channel = await seed_channel(session, suffix="web-ch")
    index = await admin_client.get("/admin/channels")
    assert index.status_code == 200
    assert channel.title in index.text

    detail = await admin_client.get(f"/admin/channels/{channel.id}")
    assert detail.status_code == 200
    assert channel.title in detail.text
    assert "Settings" in detail.text

    settings_post = await admin_client.post(
        f"/admin/channels/{channel.id}/settings",
        data={
            "csrf_token": admin_csrf,
            "ai_enabled": "true",
            "rule_auto_approve": "20",
            "rule_auto_reject": "80",
            "trust_auto_approve": "88",
            "trust_auto_reject": "12",
            "join_request_timeout_hours": "",
        },
        follow_redirects=False,
    )
    assert settings_post.status_code == 303

    disable = await admin_client.post(
        f"/admin/channels/{channel.id}/disable",
        data={"csrf_token": admin_csrf},
        follow_redirects=False,
    )
    assert disable.status_code == 303

    enable = await admin_client.post(
        f"/admin/channels/{channel.id}/enable",
        data={"csrf_token": admin_csrf},
        follow_redirects=False,
    )
    assert enable.status_code == 303


@pytest.mark.asyncio
async def test_admin_channel_service_delete(session: AsyncSession) -> None:
    channel = await seed_channel(session, suffix="svc-delete")
    service = AdminChannelService(session)
    channel_id = channel.id

    title = await service.delete_channel(channel_id)
    assert title == channel.title

    assert await service.get_channel_detail(channel_id) is None
    items = await service.list_channels()
    assert not any(item.id == channel_id for item in items)


@pytest.mark.asyncio
async def test_channels_delete_endpoints(session: AsyncSession, admin_client: AsyncClient, admin_csrf: str) -> None:
    channel = await seed_channel(session, suffix="api-delete")
    channel_id = channel.id

    delete_response = await admin_client.delete(f"/api/v1/admin/channels/{channel_id}")
    assert delete_response.status_code == 204

    missing = await admin_client.get(f"/api/v1/admin/channels/{channel_id}")
    assert missing.status_code == 404

    channel_web = await seed_channel(session, suffix="web-delete")
    delete_web = await admin_client.post(
        f"/admin/channels/{channel_web.id}/delete",
        data={"csrf_token": admin_csrf},
        follow_redirects=False,
    )
    assert delete_web.status_code == 303
    assert delete_web.headers["location"].startswith("/admin/channels?flash=success")

    index = await admin_client.get("/admin/channels")
    assert index.status_code == 200
    assert channel_web.title not in index.text
