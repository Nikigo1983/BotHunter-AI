from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.enums import DashboardRole
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DashboardUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dashboard_users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_dashboard_users_email"),
        Index("ix_dashboard_users_email", "email"),
        Index("ix_dashboard_users_role", "role"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DashboardRole.VIEWER.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
