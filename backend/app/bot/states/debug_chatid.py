from aiogram.fsm.state import State, StatesGroup


class DebugChatIdStates(StatesGroup):
    waiting_for_forward = State()
