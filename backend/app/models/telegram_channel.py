from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.channel_settings import ChannelSettings
    from app.models.join_request import JoinRequest
    from app.models.telegram_bot import TelegramBot
    from app.models.user import User


class TelegramChannel(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "telegram_channels"
    __table_args__ = (
        UniqueConstraint("telegram_chat_id", name="uq_telegram_channels_telegram_chat_id"),
        Index("ix_telegram_channels_owner_id", "owner_id"),
        Index("ix_telegram_channels_bot_id", "bot_id"),
        Index("ix_telegram_channels_telegram_chat_id", "telegram_chat_id"),
        Index("ix_telegram_channels_is_active", "is_active"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_bots.id", ondelete="CASCADE"),
        nullable=False,
    )
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invite_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    owner: Mapped[User] = relationship(back_populates="telegram_channels")
    bot: Mapped[TelegramBot] = relationship(back_populates="channels")
    settings: Mapped[ChannelSettings | None] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
        uselist=False,
    )
    join_requests: Mapped[list[JoinRequest]] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
    )
