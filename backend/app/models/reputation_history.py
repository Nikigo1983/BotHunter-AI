from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin
from app.reputation.enums import ReputationChangeReason

if TYPE_CHECKING:
    from app.models.telegram_user import TelegramUser


class ReputationHistory(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "reputation_history"
    __table_args__ = (
        Index("ix_reputation_history_telegram_user_id", "telegram_user_id"),
        Index("ix_reputation_history_reason", "reason"),
        Index("ix_reputation_history_created_at", "created_at"),
    )

    telegram_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    old_score: Mapped[float] = mapped_column(Float, nullable=False)
    new_score: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[ReputationChangeReason] = mapped_column(
        Enum(ReputationChangeReason, name="reputation_change_reason"),
        nullable=False,
    )
    actor: Mapped[str] = mapped_column(String(255), nullable=False, default="system")

    telegram_user: Mapped[TelegramUser] = relationship(back_populates="reputation_history")
