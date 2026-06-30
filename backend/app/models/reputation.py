from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.telegram_user import TelegramUser


class Reputation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reputations"
    __table_args__ = (
        UniqueConstraint("telegram_user_id", name="uq_reputations_telegram_user_id"),
        Index("ix_reputations_telegram_user_id", "telegram_user_id"),
        Index("ix_reputations_reputation_score", "reputation_score"),
    )

    telegram_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reputation_score: Mapped[float] = mapped_column(Float, default=50.0, server_default="50", nullable=False)
    bot_votes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    human_votes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_update: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    telegram_user: Mapped[TelegramUser] = relationship(back_populates="reputation")
