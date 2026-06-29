from dataclasses import dataclass

from app.models.telegram_channel import TelegramChannel


@dataclass(slots=True)
class ChannelRegistrationSuccess:
    channel: TelegramChannel
    title: str
    telegram_chat_id: int


@dataclass(slots=True)
class ChannelRegistrationFailure:
    reason: str
    telegram_chat_id: int | None = None
