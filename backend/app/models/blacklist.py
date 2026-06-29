from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.telegram_user import TelegramUser


class Blacklist(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "blacklists"
    __table_args__ = (
        Index("ix_blacklists_telegram_user_id", "telegram_user_id"),
        Index("ix_blacklists_source", "source"),
        Index("ix_blacklists_created_at", "created_at"),
    )

    telegram_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)

    telegram_user: Mapped[TelegramUser] = relationship(back_populates="blacklist_entries")
