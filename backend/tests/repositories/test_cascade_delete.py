import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_bot import TelegramBot
from app.models.telegram_channel import TelegramChannel
from app.repositories.deps import (
    get_telegram_bot_repository,
    get_telegram_channel_repository,
    get_user_repository,
)
from tests.conftest import make_user


@pytest.mark.asyncio
async def test_delete_user_cascades_to_bot_and_channel(session: AsyncSession) -> None:
    user_repo = get_user_repository(session)
    bot_repo = get_telegram_bot_repository(session)
    channel_repo = get_telegram_channel_repository(session)

    user = await user_repo.create(make_user("cascade"))
    bot = await bot_repo.create(
        TelegramBot(
            owner_id=user.id,
            bot_token="token",
            bot_username=f"cascade_bot_{uuid.uuid4().hex[:8]}",
        )
    )
    channel = await channel_repo.create(
        TelegramChannel(
            owner_id=user.id,
            bot_id=bot.id,
            telegram_chat_id=int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000,
            title="Cascade Channel",
            is_active=True,
        )
    )

    await user_repo.delete(user)

    assert await bot_repo.get_by_id(bot.id) is None
    assert await channel_repo.get_by_id(channel.id) is None
