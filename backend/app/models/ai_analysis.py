from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import AnalysisDecision
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.join_request import JoinRequest


class AIAnalysis(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "ai_analyses"
    __table_args__ = (
        Index("ix_ai_analyses_join_request_id", "join_request_id"),
        Index("ix_ai_analyses_decision", "decision"),
        Index("ix_ai_analyses_created_at", "created_at"),
    )

    join_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("join_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision: Mapped[AnalysisDecision] = mapped_column(
        Enum(AnalysisDecision, name="analysis_decision"),
        nullable=False,
    )
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    join_request: Mapped[JoinRequest] = relationship(back_populates="ai_analyses")
