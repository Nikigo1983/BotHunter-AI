from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import ChatJoinRequest

from app.bot.handlers.join_request import handle_chat_join_request


def make_event() -> AsyncMock:
    event = AsyncMock(spec=ChatJoinRequest)
    event.chat = AsyncMock(id=-100123)
    event.from_user = AsyncMock(id=555001)
    return event


@pytest.mark.asyncio
async def test_chat_join_request_handler_commits_session() -> None:
    event = make_event()
    bot = AsyncMock()

    with patch(
        "app.bot.handlers.join_request.JoinRequestProcessingService"
    ) as service_cls:
        service = AsyncMock()
        service.process = AsyncMock(return_value=None)
        service_cls.return_value = service

        with patch("app.bot.handlers.join_request.async_session_factory") as session_factory:
            session = AsyncMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=False)
            session_factory.return_value = session

            await handle_chat_join_request(event, bot)

            service.process.assert_awaited_once_with(event)
            session.commit.assert_awaited_once()
            session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_chat_join_request_handler_rolls_back_on_error() -> None:
    event = make_event()
    bot = AsyncMock()

    with patch(
        "app.bot.handlers.join_request.JoinRequestProcessingService"
    ) as service_cls:
        service = AsyncMock()
        service.process = AsyncMock(side_effect=RuntimeError("processing failed"))
        service_cls.return_value = service

        with patch("app.bot.handlers.join_request.async_session_factory") as session_factory:
            session = AsyncMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=False)
            session_factory.return_value = session

            await handle_chat_join_request(event, bot)

            session.rollback.assert_awaited_once()
            session.commit.assert_not_called()
