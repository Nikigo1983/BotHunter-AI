from app.bot.handlers.commands import router as commands_router
from app.bot.handlers.connect import router as connect_router
from app.bot.handlers.debug_chatid import router as debug_chatid_router
from app.bot.handlers.join_request import router as join_request_router

__all__ = ["commands_router", "connect_router", "debug_chatid_router", "join_request_router"]
