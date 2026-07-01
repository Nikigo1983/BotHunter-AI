import uuid
from typing import Literal

from sqlalchemy import Any, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai_analysis import AIAnalysis
from app.models.blacklist import Blacklist
from app.models.enums import JoinRequestStatus
from app.models.join_request import JoinRequest
from app.models.reputation import Reputation
from app.models.telegram_channel import TelegramChannel
from app.models.telegram_user import TelegramUser
from app.models.whitelist import Whitelist
from app.repositories.admin_dashboard_types import JoinRequestAdminRow, JoinRequestListQueryResult

StatusFilter = Literal["all", "pending", "approved", "rejected", "manual_review"]

STATUS_FILTER_MAP: dict[StatusFilter, JoinRequestStatus | None] = {
    "all": None,
    "pending": JoinRequestStatus.PENDING,
    "approved": JoinRequestStatus.APPROVED,
    "rejected": JoinRequestStatus.REJECTED,
    "manual_review": JoinRequestStatus.MANUAL_REVIEW,
}


class AdminDashboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_join_requests(
        self,
        *,
        organization_id: uuid.UUID,
        workspace_id: uuid.UUID,
        status_filter: StatusFilter = "all",
        search: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> JoinRequestListQueryResult:
        filters_stmt = self._apply_filters(
            select(JoinRequest.id),
            status_filter,
            search,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )
        count_stmt = select(func.count()).select_from(filters_stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar_one())

        rows_stmt = self._apply_filters(
            select(JoinRequest),
            status_filter,
            search,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )
        rows_stmt = (
            rows_stmt.options(
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

    async def get_join_request(
        self,
        join_request_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> JoinRequestAdminRow | None:
        stmt = (
            select(JoinRequest)
            .join(TelegramChannel, TelegramChannel.id == JoinRequest.channel_id)
            .options(
                selectinload(JoinRequest.channel),
                selectinload(JoinRequest.telegram_user),
                selectinload(JoinRequest.ai_analyses),
            )
            .where(
                JoinRequest.id == join_request_id,
                TelegramChannel.organization_id == organization_id,
                TelegramChannel.workspace_id == workspace_id,
            )
        )
        join_request = (await self._session.execute(stmt)).scalar_one_or_none()
        if join_request is None:
            return None
        return self._to_admin_row(join_request)

    async def get_statistics(self) -> dict[str, float | int | None]:
        total = int(
            (await self._session.execute(select(func.count()).select_from(JoinRequest))).scalar_one()
        )
        status_counts: dict[str, int] = {}
        for status in JoinRequestStatus:
            count = int(
                (
                    await self._session.execute(
                        select(func.count())
                        .select_from(JoinRequest)
                        .where(JoinRequest.status == status)
                    )
                ).scalar_one()
            )
            status_counts[status.value] = count

        avg_rule_score = (
            await self._session.execute(select(func.avg(AIAnalysis.rule_score)))
        ).scalar_one()
        avg_ai_score = (
            await self._session.execute(select(func.avg(AIAnalysis.ai_score)))
        ).scalar_one()
        avg_trust_score = (
            await self._session.execute(select(func.avg(Reputation.reputation_score)))
        ).scalar_one()
        from app.reputation.engine import DEFAULT_TRUST_SCORE

        if avg_trust_score is None and total > 0:
            avg_trust_score = DEFAULT_TRUST_SCORE

        return {
            "total": total,
            "approved": status_counts.get(JoinRequestStatus.APPROVED.value, 0),
            "rejected": status_counts.get(JoinRequestStatus.REJECTED.value, 0),
            "manual_review": status_counts.get(JoinRequestStatus.MANUAL_REVIEW.value, 0),
            "pending": status_counts.get(JoinRequestStatus.PENDING.value, 0),
            "avg_rule_score": float(avg_rule_score) if avg_rule_score is not None else None,
            "avg_ai_score": float(avg_ai_score) if avg_ai_score is not None else None,
            "avg_trust_score": float(avg_trust_score) if avg_trust_score is not None else None,
        }

    def _apply_filters(
        self,
        stmt: Select[Any],
        status_filter: StatusFilter,
        search: str | None,
        *,
        organization_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Select[Any]:
        stmt = stmt.join(TelegramChannel, JoinRequest.channel_id == TelegramChannel.id).where(
            TelegramChannel.organization_id == organization_id,
            TelegramChannel.workspace_id == workspace_id,
        )
        mapped_status = STATUS_FILTER_MAP.get(status_filter)
        if mapped_status is not None:
            stmt = stmt.where(JoinRequest.status == mapped_status)

        cleaned = (search or "").strip()
        if cleaned:
            stmt = stmt.join(TelegramUser, JoinRequest.telegram_user_id == TelegramUser.id)
            conditions = [
                TelegramChannel.title.ilike(f"%{cleaned}%"),
                TelegramUser.username.ilike(f"%{cleaned}%"),
            ]
            if cleaned.isdigit():
                conditions.append(TelegramUser.telegram_id == int(cleaned))
            stmt = stmt.where(or_(*conditions))
        return stmt

    async def get_user_list_flags(
        self,
        telegram_user_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, tuple[bool, bool]]:
        if not telegram_user_ids:
            return {}

        whitelist_stmt = select(Whitelist.telegram_user_id).where(
            Whitelist.telegram_user_id.in_(telegram_user_ids)
        )
        blacklist_stmt = select(Blacklist.telegram_user_id).where(
            Blacklist.telegram_user_id.in_(telegram_user_ids)
        )
        whitelisted = set((await self._session.execute(whitelist_stmt)).scalars().all())
        blacklisted = set((await self._session.execute(blacklist_stmt)).scalars().all())

        return {
            user_id: (user_id in whitelisted, user_id in blacklisted)
            for user_id in telegram_user_ids
        }

    async def get_trust_scores(
        self,
        telegram_user_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, float]:
        if not telegram_user_ids:
            return {}

        stmt = select(Reputation.telegram_user_id, Reputation.reputation_score).where(
            Reputation.telegram_user_id.in_(telegram_user_ids)
        )
        rows = (await self._session.execute(stmt)).all()
        from app.reputation.engine import DEFAULT_TRUST_SCORE

        scores = {row[0]: float(row[1]) for row in rows}
        return {
            user_id: scores.get(user_id, DEFAULT_TRUST_SCORE)
            for user_id in telegram_user_ids
        }

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
