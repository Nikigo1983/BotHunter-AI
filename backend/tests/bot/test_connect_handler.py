import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from unittest.mock import AsyncMock, MagicMock

from app.bot.handlers.connect import CONNECT_INSTRUCTIONS, handle_connect
from app.bot.states.connect import ConnectChannelStates


@pytest.mark.asyncio
async def test_connect_command_sets_state_and_sends_instructions() -> None:
    message = MagicMock()
    message.answer = AsyncMock()

    storage = MemoryStorage()
    state = FSMContext(
        storage=storage,
        key=StorageKey(bot_id=456, chat_id=123, user_id=123),
    )

    await handle_connect(message, state)

    current_state = await state.get_state()
    assert current_state == ConnectChannelStates.waiting_for_channel_id.state
    message.answer.assert_awaited_once_with(CONNECT_INSTRUCTIONS)
