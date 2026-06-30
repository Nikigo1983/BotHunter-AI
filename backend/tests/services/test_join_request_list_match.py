import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, ChatJoinRequest, User as TelegramProfile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blacklist import Blacklist
from app.models.enums import AnalysisDecision, JoinRequestStatus
from app.models.telegram_user import TelegramUser
from app.models.whitelist import Whitelist
from app.repositories.deps import (
    get_blacklist_repository,
    get_join_request_repository,
    get_whitelist_repository,
)
from app.services.join_request_processing import JoinRequestProcessingService
from tests.services.test_join_request_processing import create_registered_channel, make_service


def make_event(*, chat_id: int, user_id: int = 930001) -> ChatJoinRequest:
    return ChatJoinRequest(
        chat=Chat(id=chat_id, type=ChatType.CHANNEL, title="List Match Channel"),
        from_user=TelegramProfile(
            id=user_id,
            is_bot=False,
            first_name="List",
            last_name="User",
            username="list_user",
            language_code="ru",
            is_premium=False,
        ),
        user_chat_id=user_id,
        date=int(datetime.now(timezone.utc).timestamp()),
        bio=None,
    )


@pytest.mark.asyncio
async def test_whitelist_auto_approve_in_join_pipeline(session: AsyncSession) -> None:
    chat_id = -100930001
    await create_registered_channel(session, chat_id)

    telegram_user = TelegramUser(
        telegram_id=930001,
        username="whitelist_user",
        first_name="White",
        last_name="List",
        language_code="ru",
        is_premium=False,
        has_photo=False,
    )
    from app.repositories.deps import get_telegram_user_repository

    telegram_user = await get_telegram_user_repository(session).create(telegram_user)
    await get_whitelist_repository(session).create(
        Whitelist(telegram_user_id=telegram_user.id, approved_by=None)
    )

    mock_bot = AsyncMock()
    mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=0)
    service = make_service(session, mock_bot)

    result = await service.process(make_event(chat_id=chat_id, user_id=930001))

    assert result is not None
    assert result.decision == AnalysisDecision.APPROVED
    assert result.join_request.status == JoinRequestStatus.APPROVED
    assert result.analysis.explanation == "whitelist_match"
    mock_bot.approve_chat_join_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_blacklist_auto_reject_in_join_pipeline(session: AsyncSession) -> None:
    chat_id = -100930002
    await create_registered_channel(session, chat_id)

    telegram_user = TelegramUser(
        telegram_id=930002,
        username="blacklist_user",
        first_name="Black",
        last_name="List",
        language_code="ru",
        is_premium=False,
        has_photo=False,
    )
    from app.repositories.deps import get_telegram_user_repository

    telegram_user = await get_telegram_user_repository(session).create(telegram_user)
    await get_blacklist_repository(session).create(
        Blacklist(
            telegram_user_id=telegram_user.id,
            reason="test",
            confidence=1.0,
            source="test",
        )
    )

    mock_bot = AsyncMock()
    mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=0)
    service = make_service(session, mock_bot)

    result = await service.process(make_event(chat_id=chat_id, user_id=930002))

    assert result is not None
    assert result.decision == AnalysisDecision.REJECTED
    assert result.join_request.status == JoinRequestStatus.REJECTED
    assert result.analysis.explanation == "blacklist_match"
    mock_bot.decline_chat_join_request.assert_awaited_once()
