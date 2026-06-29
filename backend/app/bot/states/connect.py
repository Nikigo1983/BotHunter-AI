from aiogram.fsm.state import State, StatesGroup


class ConnectChannelStates(StatesGroup):
    waiting_for_channel_id = State()
