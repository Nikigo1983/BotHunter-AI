from sqlalchemy import BigInteger, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class ChannelConnectionError(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "channel_connection_errors"
    __table_args__ = (
        Index("ix_channel_connection_errors_telegram_id", "telegram_id"),
        Index("ix_channel_connection_errors_channel_id", "channel_id"),
        Index("ix_channel_connection_errors_created_at", "created_at"),
    )

    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
