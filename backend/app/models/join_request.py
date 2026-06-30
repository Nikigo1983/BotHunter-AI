from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import JoinRequestStatus
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.ai_analysis import AIAnalysis
    from app.models.ai_feedback import AIFeedback
    from app.models.manual_review import ManualReview
    from app.models.telegram_channel import TelegramChannel
    from app.models.telegram_user import TelegramUser


class JoinRequest(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "join_requests"
    __table_args__ = (
        Index("ix_join_requests_channel_id", "channel_id"),
        Index("ix_join_requests_telegram_user_id", "telegram_user_id"),
        Index("ix_join_requests_status", "status"),
        Index(
            "ix_join_requests_channel_user_created",
            "channel_id",
            "telegram_user_id",
            "created_at",
        ),
    )

    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    telegram_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[JoinRequestStatus] = mapped_column(
        Enum(JoinRequestStatus, name="join_request_status"),
        default=JoinRequestStatus.PENDING,
        nullable=False,
    )

    channel: Mapped[TelegramChannel] = relationship(back_populates="join_requests")
    telegram_user: Mapped[TelegramUser] = relationship(back_populates="join_requests")
    ai_analyses: Mapped[list[AIAnalysis]] = relationship(
        back_populates="join_request",
        cascade="all, delete-orphan",
    )
    manual_reviews: Mapped[list[ManualReview]] = relationship(
        back_populates="join_request",
        cascade="all, delete-orphan",
    )
    ai_feedbacks: Mapped[list[AIFeedback]] = relationship(
        back_populates="join_request",
        cascade="all, delete-orphan",
    )
