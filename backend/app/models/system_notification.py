from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class SystemNotification(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "system_notifications"
    __table_args__ = (
        Index("ix_system_notifications_level", "level"),
        Index("ix_system_notifications_is_read", "is_read"),
        Index("ix_system_notifications_created_at", "created_at"),
    )

    level: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
