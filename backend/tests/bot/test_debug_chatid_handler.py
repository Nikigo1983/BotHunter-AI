from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from aiogram.enums import ChatType, MessageOriginType
from aiogram.types import Chat, MessageOriginChannel, MessageOriginChat

from app.bot.handlers.debug_chatid import _format_chat_type, _resolve_forward_source

NOW = datetime.now(timezone.utc)


def test_resolve_forward_source_from_channel_origin() -> None:
    message = MagicMock()
    message.forward_origin = MessageOriginChannel(
        type=MessageOriginType.CHANNEL,
        chat=Chat(id=-1001234567890, type=ChatType.CHANNEL, title="Test Channel"),
        message_id=42,
        date=NOW,
    )
    message.forward_from_chat = None
    message.forward_from = None
    message.forward_sender_name = None
    message.forward_date = None
    message.forward_signature = None

    chat, reason = _resolve_forward_source(message)

    assert chat is not None
    assert chat.id == -1001234567890
    assert reason is None


def test_resolve_forward_source_not_a_forward() -> None:
    message = MagicMock()
    message.forward_origin = None
    message.forward_from_chat = None
    message.forward_from = None
    message.forward_sender_name = None
    message.forward_date = None
    message.forward_signature = None

    chat, reason = _resolve_forward_source(message)

    assert chat is None
    assert reason is not None
    assert "не пересланное" in reason.lower()


def test_resolve_forward_source_from_supergroup() -> None:
    group_chat = Chat(id=-100999, type=ChatType.SUPERGROUP, title="Group")
    message = MagicMock()
    message.forward_origin = MessageOriginChat(
        type=MessageOriginType.CHAT,
        chat=group_chat,
        message_id=1,
        date=NOW,
        sender_chat=group_chat,
    )
    message.forward_from_chat = None
    message.forward_from = None
    message.forward_sender_name = None
    message.forward_date = None
    message.forward_signature = None

    chat, reason = _resolve_forward_source(message)

    assert chat is None
    assert reason is not None
    assert "не из канала" in reason.lower() or "группы" in reason.lower()


def test_format_chat_type() -> None:
    assert _format_chat_type(ChatType.CHANNEL) == "channel"
