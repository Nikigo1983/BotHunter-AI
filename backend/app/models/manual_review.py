from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import AnalysisDecision
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.join_request import JoinRequest
    from app.models.telegram_user import TelegramUser


class AdminAction(str, enum.Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    WHITELIST = "WHITELIST"
    BLACKLIST = "BLACKLIST"


class ManualReview(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "manual_reviews"
    __table_args__ = (
        Index("ix_manual_reviews_join_request_id", "join_request_id"),
        Index("ix_manual_reviews_telegram_user_id", "telegram_user_id"),
        Index("ix_manual_reviews_admin_action", "admin_action"),
        Index("ix_manual_reviews_created_at", "created_at"),
    )

    join_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("join_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    telegram_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    admin_action: Mapped[AdminAction] = mapped_column(
        Enum(AdminAction, name="admin_action"),
        nullable=False,
    )
    previous_decision: Mapped[AnalysisDecision] = mapped_column(
        Enum(AnalysisDecision, name="analysis_decision"),
        nullable=False,
    )
    final_decision: Mapped[AnalysisDecision] = mapped_column(
        Enum(AnalysisDecision, name="analysis_decision"),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    join_request: Mapped[JoinRequest] = relationship(back_populates="manual_reviews")
    telegram_user: Mapped[TelegramUser] = relationship(back_populates="manual_reviews")
