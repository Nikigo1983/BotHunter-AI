import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_analysis import AIAnalysis
from app.models.audit_log import AuditLog
from app.models.blacklist import Blacklist
from app.models.enums import AnalysisDecision, JoinRequestStatus
from app.models.join_request import JoinRequest
from app.models.reputation import Reputation
from app.models.telegram_bot import TelegramBot
from app.models.telegram_channel import TelegramChannel
from app.models.telegram_user import TelegramUser
from app.models.whitelist import Whitelist
from app.repositories.deps import (
    get_ai_analysis_repository,
    get_audit_log_repository,
    get_blacklist_repository,
    get_join_request_repository,
    get_reputation_repository,
    get_telegram_bot_repository,
    get_telegram_channel_repository,
    get_telegram_user_repository,
    get_user_repository,
    get_whitelist_repository,
)
from tests.conftest import make_user


@pytest.mark.asyncio
async def test_user_repository_crud(session: AsyncSession) -> None:
    repo = get_user_repository(session)
    user = make_user("crud")

    created = await repo.create(user)
    assert created.id is not None
    assert await repo.exists(created.id) is True
    assert await repo.count() >= 1

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.email == user.email

    fetched.full_name = "Updated Name"
    updated = await repo.update(fetched)
    assert updated.full_name == "Updated Name"

    all_users = await repo.get_all(limit=1000)
    assert any(item.id == created.id for item in all_users)

    assert await repo.delete_by_id(created.id) is True
    assert await repo.exists(created.id) is False
    assert await repo.get_by_id(created.id) is None


@pytest.mark.asyncio
async def test_all_repositories_create_and_get(session: AsyncSession) -> None:
    user_repo = get_user_repository(session)
    bot_repo = get_telegram_bot_repository(session)
    channel_repo = get_telegram_channel_repository(session)
    telegram_user_repo = get_telegram_user_repository(session)
    join_request_repo = get_join_request_repository(session)
    ai_analysis_repo = get_ai_analysis_repository(session)
    blacklist_repo = get_blacklist_repository(session)
    whitelist_repo = get_whitelist_repository(session)
    reputation_repo = get_reputation_repository(session)
    audit_log_repo = get_audit_log_repository(session)

    user = await user_repo.create(make_user("all"))
    bot = await bot_repo.create(
        TelegramBot(
            owner_id=user.id,
            bot_token="token",
            bot_username=f"bot_{uuid.uuid4().hex[:8]}",
        )
    )
    channel = await channel_repo.create(
        TelegramChannel(
            owner_id=user.id,
            bot_id=bot.id,
            telegram_chat_id=int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000,
            title="Test Channel",
            invite_link="https://t.me/test",
            is_active=True,
        )
    )
    telegram_user = await telegram_user_repo.create(
        TelegramUser(
            telegram_id=int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000,
            username="tg_user",
            first_name="First",
            last_name="Last",
            language_code="ru",
            is_premium=False,
            has_photo=True,
        )
    )
    join_request = await join_request_repo.create(
        JoinRequest(
            channel_id=channel.id,
            telegram_user_id=telegram_user.id,
            status=JoinRequestStatus.PENDING,
        )
    )
    ai_analysis = await ai_analysis_repo.create(
        AIAnalysis(
            join_request_id=join_request.id,
            rule_score=0.2,
            ai_score=0.8,
            final_score=0.65,
            decision=AnalysisDecision.MANUAL_REVIEW,
            explanation="Test analysis",
        )
    )
    blacklist = await blacklist_repo.create(
        Blacklist(
            telegram_user_id=telegram_user.id,
            reason="spam",
            confidence=0.95,
            source="manual",
        )
    )
    whitelist = await whitelist_repo.create(
        Whitelist(
            telegram_user_id=telegram_user.id,
            approved_by=user.id,
        )
    )
    reputation = await reputation_repo.create(
        Reputation(
            telegram_user_id=telegram_user.id,
            reputation_score=4.5,
            bot_votes=1,
            human_votes=2,
        )
    )
    audit_log = await audit_log_repo.create(
        AuditLog(
            actor=str(user.id),
            action="create",
            entity="user",
            entity_id=user.id,
        )
    )

    assert await user_repo.get_by_id(user.id) is not None
    assert await bot_repo.get_by_id(bot.id) is not None
    assert await channel_repo.get_by_id(channel.id) is not None
    assert await telegram_user_repo.get_by_id(telegram_user.id) is not None
    assert await join_request_repo.get_by_id(join_request.id) is not None
    assert await ai_analysis_repo.get_by_id(ai_analysis.id) is not None
    assert await blacklist_repo.get_by_id(blacklist.id) is not None
    assert await whitelist_repo.get_by_id(whitelist.id) is not None
    assert await reputation_repo.get_by_id(reputation.id) is not None
    assert await audit_log_repo.get_by_id(audit_log.id) is not None
