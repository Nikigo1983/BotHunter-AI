from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.telegram_bot import TelegramBot
    from app.models.telegram_channel import TelegramChannel
    from app.models.whitelist import Whitelist


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
        Index("ix_users_email", "email"),
        Index("ix_users_telegram_id", "telegram_id"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    telegram_bots: Mapped[list[TelegramBot]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    telegram_channels: Mapped[list[TelegramChannel]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    whitelist_approvals: Mapped[list[Whitelist]] = relationship(
        back_populates="approved_by_user",
    )
