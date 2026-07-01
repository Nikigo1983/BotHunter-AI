import uuid

from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class PolicyThresholdConfigModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "policy_threshold_configs"

    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    approve_below: Mapped[int] = mapped_column(Integer, nullable=False)
    reject_from: Mapped[int] = mapped_column(Integer, nullable=False)
    trust_auto_approve: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    trust_auto_reject: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    ai_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.75)
