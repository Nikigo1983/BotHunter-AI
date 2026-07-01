from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.telegram_channel import TelegramChannel


class ChannelSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "channel_settings"
    __table_args__ = (UniqueConstraint("channel_id", name="uq_channel_settings_channel_id"),)

    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rule_auto_approve: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    rule_auto_reject: Mapped[int] = mapped_column(Integer, default=70, nullable=False)
    trust_auto_approve: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    trust_auto_reject: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    join_request_timeout_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)

    channel: Mapped[TelegramChannel] = relationship(back_populates="settings")
