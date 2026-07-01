import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class PolicyRuleConfig(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "policy_rule_configs"
    __table_args__ = (
        UniqueConstraint("version_id", "rule_key", name="uq_policy_rule_configs_version_rule"),
        Index("ix_policy_rule_configs_rule_key", "rule_key"),
    )

    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_key: Mapped[str] = mapped_column(String(128), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    admin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
