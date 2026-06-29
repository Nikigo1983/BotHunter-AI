from aiogram import Bot, Router
from aiogram.types import ChatJoinRequest

from app.database.session import async_session_factory
from app.services.join_request_processing import JoinRequestProcessingService
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = Router(name="join_request")


@router.chat_join_request()
async def handle_chat_join_request(event: ChatJoinRequest, bot: Bot) -> None:
    chat_id = event.chat.id if event.chat else "unknown"
    user_id = event.from_user.id if event.from_user else "unknown"

    async with async_session_factory() as session:
        try:
            service = JoinRequestProcessingService(session, bot)
            await service.process(event)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error(
                "Join request processing failed | chat_id=%s user_id=%s error=%s",
                chat_id,
                user_id,
                exc,
                exc_info=True,
            )
