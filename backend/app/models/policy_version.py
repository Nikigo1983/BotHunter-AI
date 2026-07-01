import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class PolicyVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "version_number",
            name="uq_policy_versions_org_version",
        ),
        Index("ix_policy_versions_organization_id", "organization_id"),
        Index("ix_policy_versions_is_current", "is_current"),
        Index("ix_policy_versions_created_at", "created_at"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    author: Mapped[str] = mapped_column(String(320), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
