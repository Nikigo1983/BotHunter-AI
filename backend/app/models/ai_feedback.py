from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import AnalysisDecision
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.join_request import JoinRequest


class AIFeedback(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "ai_feedbacks"
    __table_args__ = (
        Index("ix_ai_feedbacks_join_request_id", "join_request_id"),
        Index("ix_ai_feedbacks_was_ai_correct", "was_ai_correct"),
        Index("ix_ai_feedbacks_created_at", "created_at"),
    )

    join_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("join_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_decision: Mapped[AnalysisDecision] = mapped_column(
        Enum(AnalysisDecision, name="analysis_decision"),
        nullable=False,
    )
    human_decision: Mapped[AnalysisDecision] = mapped_column(
        Enum(AnalysisDecision, name="analysis_decision"),
        nullable=False,
    )
    was_ai_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    join_request: Mapped[JoinRequest] = relationship(back_populates="ai_feedbacks")
