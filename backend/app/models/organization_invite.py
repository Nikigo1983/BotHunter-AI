from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.enums import DashboardRole, InviteStatus
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class OrganizationInvite(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "organization_invites"
    __table_args__ = (
        UniqueConstraint("token", name="uq_organization_invites_token"),
        Index("ix_organization_invites_organization_id", "organization_id"),
        Index("ix_organization_invites_email", "email"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DashboardRole.MODERATOR.value,
    )
    token: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=InviteStatus.PENDING.value,
    )
    invited_by: Mapped[str] = mapped_column(String(320), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
