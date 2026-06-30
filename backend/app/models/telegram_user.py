from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.blacklist import Blacklist
    from app.models.join_request import JoinRequest
    from app.models.manual_review import ManualReview
    from app.models.reputation import Reputation
    from app.models.whitelist import Whitelist


class TelegramUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "telegram_users"
    __table_args__ = (
        UniqueConstraint("telegram_id", name="uq_telegram_users_telegram_id"),
        Index("ix_telegram_users_telegram_id", "telegram_id"),
        Index("ix_telegram_users_username", "username"),
    )

    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_photo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    join_requests: Mapped[list[JoinRequest]] = relationship(
        back_populates="telegram_user",
        cascade="all, delete-orphan",
    )
    reputation: Mapped[Reputation | None] = relationship(
        back_populates="telegram_user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    blacklist_entries: Mapped[list[Blacklist]] = relationship(
        back_populates="telegram_user",
        cascade="all, delete-orphan",
    )
    whitelist_entries: Mapped[list[Whitelist]] = relationship(
        back_populates="telegram_user",
        cascade="all, delete-orphan",
    )
    manual_reviews: Mapped[list[ManualReview]] = relationship(
        back_populates="telegram_user",
        cascade="all, delete-orphan",
    )
