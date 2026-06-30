import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from app.bot.states.connect import ConnectChannelStates
from app.bot.storage import create_fsm_storage


@pytest.mark.asyncio
async def test_redis_fsm_storage_persists_state_across_contexts() -> None:
    storage = create_fsm_storage()
    key = StorageKey(bot_id=8389397180, chat_id=900001, user_id=900001)

    try:
        first_context = FSMContext(storage=storage, key=key)
        await first_context.set_state(ConnectChannelStates.waiting_for_channel_id)

        second_context = FSMContext(storage=storage, key=key)
        assert (
            await second_context.get_state()
            == ConnectChannelStates.waiting_for_channel_id.state
        )

        await second_context.clear()
        assert await first_context.get_state() is None
    finally:
        await storage.close()
