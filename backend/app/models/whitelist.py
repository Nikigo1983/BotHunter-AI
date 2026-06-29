from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.telegram_user import TelegramUser
    from app.models.user import User


class Whitelist(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "whitelists"
    __table_args__ = (
        Index("ix_whitelists_telegram_user_id", "telegram_user_id"),
        Index("ix_whitelists_approved_by", "approved_by"),
        Index("ix_whitelists_created_at", "created_at"),
    )

    telegram_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    telegram_user: Mapped[TelegramUser] = relationship(back_populates="whitelist_entries")
    approved_by_user: Mapped[User | None] = relationship(back_populates="whitelist_approvals")
