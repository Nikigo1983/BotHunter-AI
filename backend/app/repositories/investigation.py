import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai_analysis import AIAnalysis
from app.models.ai_feedback import AIFeedback
from app.models.audit_log import AuditLog
from app.models.enums import AnalysisDecision, JoinRequestStatus
from app.models.join_request import JoinRequest
from app.models.reputation import Reputation
from app.models.telegram_channel import TelegramChannel
from app.models.telegram_user import TelegramUser
from app.repositories.admin_dashboard_types import JoinRequestAdminRow, JoinRequestListQueryResult

InvestigationStatusFilter = Literal[
    "all", "pending", "approved", "rejected", "manual_review"
]

STATUS_FILTER_MAP: dict[InvestigationStatusFilter, JoinRequestStatus | None] = {
    "all": None,
    "pending": JoinRequestStatus.PENDING,
    "approved": JoinRequestStatus.APPROVED,
    "rejected": JoinRequestStatus.REJECTED,
    "manual_review": JoinRequestStatus.MANUAL_REVIEW,
}


@dataclass(slots=True)
class InvestigationFilters:
    channel_id: uuid.UUID | None = None
    status: InvestigationStatusFilter = "all"
    ai_decision: AnalysisDecision | None = None
    human_decision: AnalysisDecision | None = None
    trust_min: float | None = None
    trust_max: float | None = None
    rule_min: float | None = None
    rule_max: float | None = None
    ai_min: float | None = None
    ai_max: float | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    search: str | None = None


class InvestigationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_investigations(
        self,
        *,
        filters: InvestigationFilters,
        offset: int = 0,
        limit: int = 25,
    ) -> JoinRequestListQueryResult:
        latest_analysis = self._latest_analysis_subquery()
        latest_feedback = self._latest_feedback_subquery()

        base_stmt = (
            select(JoinRequest)
            .join(TelegramChannel, JoinRequest.channel_id == TelegramChannel.id)
            .join(TelegramUser, JoinRequest.telegram_user_id == TelegramUser.id)
            .outerjoin(latest_analysis, latest_analysis.c.join_request_id == JoinRequest.id)
            .outerjoin(Reputation, Reputation.telegram_user_id == TelegramUser.id)
            .outerjoin(latest_feedback, latest_feedback.c.join_request_id == JoinRequest.id)
        )
        filtered = self._apply_filters(base_stmt, filters, latest_analysis, latest_feedback)

        count_stmt = select(func.count()).select_from(filtered.subquery())
        total = int((await self._session.execute(count_stmt)).scalar_one())

        rows_stmt = (
            filtered.options(
                selectinload(JoinRequest.channel),
                selectinload(JoinRequest.telegram_user),
                selectinload(JoinRequest.ai_analyses),
            )
            .order_by(JoinRequest.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        join_requests = list((await self._session.execute(rows_stmt)).scalars().unique().all())
        rows = [self._to_admin_row(item) for item in join_requests]
        return JoinRequestListQueryResult(rows=rows, total=total)

    async def get_investigation(self, join_request_id: uuid.UUID) -> JoinRequestAdminRow | None:
        stmt = (
            select(JoinRequest)
            .options(
                selectinload(JoinRequest.channel),
                selectinload(JoinRequest.telegram_user),
                selectinload(JoinRequest.ai_analyses),
            )
            .where(JoinRequest.id == join_request_id)
        )
        join_request = (await self._session.execute(stmt)).scalar_one_or_none()
        if join_request is None:
            return None
        return self._to_admin_row(join_request)

    async def list_audit_logs(self, join_request_id: uuid.UUID) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.entity == "join_request",
                AuditLog.entity_id == join_request_id,
            )
            .order_by(AuditLog.created_at.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_channels_for_filter(self) -> list[tuple[uuid.UUID, str]]:
        stmt = select(TelegramChannel.id, TelegramChannel.title).order_by(TelegramChannel.title)
        rows = (await self._session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]

    async def get_latest_feedback(self, join_request_id: uuid.UUID) -> AIFeedback | None:
        stmt = (
            select(AIFeedback)
            .where(AIFeedback.join_request_id == join_request_id)
            .order_by(AIFeedback.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    def _latest_analysis_subquery(self):
        ranked = (
            select(
                AIAnalysis.join_request_id.label("join_request_id"),
                AIAnalysis.rule_score.label("rule_score"),
                AIAnalysis.ai_score.label("ai_score"),
                AIAnalysis.decision.label("decision"),
                AIAnalysis.created_at.label("created_at"),
                func.row_number()
                .over(
                    partition_by=AIAnalysis.join_request_id,
                    order_by=AIAnalysis.created_at.desc(),
                )
                .label("row_num"),
            )
        ).subquery()
        return (
            select(
                ranked.c.join_request_id,
                ranked.c.rule_score,
                ranked.c.ai_score,
                ranked.c.decision,
                ranked.c.created_at,
            )
            .where(ranked.c.row_num == 1)
            .subquery("latest_analysis")
        )

    def _latest_feedback_subquery(self):
        ranked = (
            select(
                AIFeedback.join_request_id.label("join_request_id"),
                AIFeedback.human_decision.label("human_decision"),
                AIFeedback.ai_decision.label("ai_decision"),
                func.row_number()
                .over(
                    partition_by=AIFeedback.join_request_id,
                    order_by=AIFeedback.created_at.desc(),
                )
                .label("row_num"),
            )
        ).subquery()
        return (
            select(
                ranked.c.join_request_id,
                ranked.c.human_decision,
                ranked.c.ai_decision,
            )
            .where(ranked.c.row_num == 1)
            .subquery("latest_feedback")
        )

    def _apply_filters(
        self,
        stmt: Select[Any],
        filters: InvestigationFilters,
        latest_analysis,
        latest_feedback,
    ) -> Select[Any]:
        mapped_status = STATUS_FILTER_MAP.get(filters.status)
        if mapped_status is not None:
            stmt = stmt.where(JoinRequest.status == mapped_status)

        if filters.channel_id is not None:
            stmt = stmt.where(JoinRequest.channel_id == filters.channel_id)

        if filters.date_from is not None:
            stmt = stmt.where(JoinRequest.created_at >= filters.date_from)
        if filters.date_to is not None:
            stmt = stmt.where(JoinRequest.created_at <= filters.date_to)

        if filters.ai_decision is not None:
            stmt = stmt.where(latest_analysis.c.decision == filters.ai_decision)

        if filters.human_decision is not None:
            stmt = stmt.where(latest_feedback.c.human_decision == filters.human_decision)

        if filters.rule_min is not None:
            stmt = stmt.where(latest_analysis.c.rule_score >= filters.rule_min)
        if filters.rule_max is not None:
            stmt = stmt.where(latest_analysis.c.rule_score <= filters.rule_max)

        if filters.ai_min is not None:
            stmt = stmt.where(latest_analysis.c.ai_score >= filters.ai_min)
        if filters.ai_max is not None:
            stmt = stmt.where(latest_analysis.c.ai_score <= filters.ai_max)

        if filters.trust_min is not None:
            stmt = stmt.where(Reputation.reputation_score >= filters.trust_min)
        if filters.trust_max is not None:
            stmt = stmt.where(Reputation.reputation_score <= filters.trust_max)

        cleaned = (filters.search or "").strip()
        if cleaned:
            conditions = [
                TelegramUser.username.ilike(f"%{cleaned}%"),
                TelegramUser.first_name.ilike(f"%{cleaned}%"),
                TelegramUser.last_name.ilike(f"%{cleaned}%"),
                TelegramChannel.title.ilike(f"%{cleaned}%"),
            ]
            if cleaned.isdigit():
                conditions.append(TelegramUser.telegram_id == int(cleaned))
            stmt = stmt.where(or_(*conditions))

        return stmt

    @staticmethod
    def _to_admin_row(join_request: JoinRequest) -> JoinRequestAdminRow:
        analysis = None
        if join_request.ai_analyses:
            analysis = max(join_request.ai_analyses, key=lambda item: item.created_at)
        return JoinRequestAdminRow(
            join_request=join_request,
            channel=join_request.channel,
            telegram_user=join_request.telegram_user,
            analysis=analysis,
        )
