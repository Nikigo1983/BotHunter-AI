from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.enums import OrganizationSecretType
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class OrganizationSecret(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organization_secrets"
    __table_args__ = (
        UniqueConstraint("organization_id", "secret_type", name="uq_org_secrets_org_type"),
        Index("ix_organization_secrets_organization_id", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    secret_type: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
