from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class SystemError(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "system_errors"
    __table_args__ = (
        Index("ix_system_errors_source", "source"),
        Index("ix_system_errors_created_at", "created_at"),
    )

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
