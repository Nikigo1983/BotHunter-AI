from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.telegram_channel import TelegramChannel
    from app.models.user import User


class TelegramBot(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "telegram_bots"
    __table_args__ = (
        UniqueConstraint("bot_username", name="uq_telegram_bots_bot_username"),
        Index("ix_telegram_bots_owner_id", "owner_id"),
        Index("ix_telegram_bots_bot_username", "bot_username"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    bot_token: Mapped[str] = mapped_column(String(255), nullable=False)
    bot_username: Mapped[str] = mapped_column(String(255), nullable=False)

    owner: Mapped[User] = relationship(back_populates="telegram_bots")
    channels: Mapped[list[TelegramChannel]] = relationship(
        back_populates="bot",
        cascade="all, delete-orphan",
    )
