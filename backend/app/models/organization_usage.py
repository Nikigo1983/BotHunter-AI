from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.enums import UsageMetric
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class OrganizationUsage(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "organization_usage"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "metric",
            "period_start",
            name="uq_organization_usage_org_metric_period",
        ),
        Index("ix_organization_usage_organization_id", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    int_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    float_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
