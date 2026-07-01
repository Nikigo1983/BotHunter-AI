import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Float, case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai_analysis import AIAnalysis
from app.models.ai_feedback import AIFeedback
from app.models.ai_usage import AIUsage
from app.models.blacklist import Blacklist
from app.models.enums import JoinRequestStatus
from app.models.join_request import JoinRequest
from app.models.reputation import Reputation
from app.models.telegram_channel import TelegramChannel
from app.models.whitelist import Whitelist


class ChannelStatisticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_channel_summaries(self) -> list[dict[str, Any]]:
        query = text(
            """
            SELECT
                c.id,
                c.title,
                c.telegram_chat_id,
                c.username,
                c.is_active,
                c.created_at,
                COUNT(jr.id) AS total_requests,
                SUM(CASE WHEN jr.status::text = 'APPROVED' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN jr.status::text = 'REJECTED' THEN 1 ELSE 0 END) AS rejected,
                SUM(CASE WHEN jr.status::text = 'MANUAL_REVIEW' THEN 1 ELSE 0 END) AS manual_review,
                AVG(a.rule_score) AS avg_rule_score,
                AVG(a.ai_score) AS avg_ai_score,
                AVG(r.reputation_score) AS avg_trust_score
            FROM telegram_channels c
            LEFT JOIN join_requests jr ON jr.channel_id = c.id
            LEFT JOIN ai_analyses a ON a.join_request_id = jr.id
            LEFT JOIN telegram_users tu ON tu.id = jr.telegram_user_id
            LEFT JOIN reputations r ON r.telegram_user_id = tu.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        )
        rows = (await self._session.execute(query)).all()
        return [dict(row._mapping) for row in rows]

    async def get_channel_summary(self, channel_id: uuid.UUID) -> dict[str, Any] | None:
        query = text(
            """
            SELECT
                c.id,
                c.title,
                c.telegram_chat_id,
                c.username,
                c.is_active,
                c.created_at,
                c.invite_link,
                COUNT(jr.id) AS total_requests,
                SUM(CASE WHEN jr.status::text = 'APPROVED' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN jr.status::text = 'REJECTED' THEN 1 ELSE 0 END) AS rejected,
                SUM(CASE WHEN jr.status::text = 'MANUAL_REVIEW' THEN 1 ELSE 0 END) AS manual_review,
                SUM(CASE WHEN jr.status::text = 'PENDING' THEN 1 ELSE 0 END) AS pending,
                AVG(a.rule_score) AS avg_rule_score,
                AVG(a.ai_score) AS avg_ai_score,
                AVG(r.reputation_score) AS avg_trust_score,
                MAX(jr.created_at) AS last_activity_at,
                COUNT(DISTINCT CASE WHEN w.id IS NOT NULL THEN tu.id END) AS whitelist_count,
                COUNT(DISTINCT CASE WHEN b.id IS NOT NULL THEN tu.id END) AS blacklist_count
            FROM telegram_channels c
            LEFT JOIN join_requests jr ON jr.channel_id = c.id
            LEFT JOIN ai_analyses a ON a.join_request_id = jr.id
            LEFT JOIN telegram_users tu ON tu.id = jr.telegram_user_id
            LEFT JOIN reputations r ON r.telegram_user_id = tu.id
            LEFT JOIN whitelists w ON w.telegram_user_id = tu.id
            LEFT JOIN blacklists b ON b.telegram_user_id = tu.id
            WHERE c.id = :channel_id
            GROUP BY c.id
            """
        )
        row = (await self._session.execute(query, {"channel_id": channel_id})).one_or_none()
        if row is None:
            return None
        return dict(row._mapping)

    async def get_channel_accuracy(self, channel_id: uuid.UUID) -> dict[str, Any]:
        stmt = (
            select(
                func.count().label("total"),
                func.sum(case((AIFeedback.was_ai_correct.is_(True), 1), else_=0)).label("matched"),
            )
            .select_from(AIFeedback)
            .join(JoinRequest, JoinRequest.id == AIFeedback.join_request_id)
            .where(JoinRequest.channel_id == channel_id)
        )
        row = (await self._session.execute(stmt)).one()
        total = int(row.total or 0)
        matched = int(row.matched or 0)
        return {
            "total": total,
            "matched": matched,
            "accuracy_percent": round(matched / total * 100, 2) if total else None,
        }

    async def list_recent_join_requests(
        self,
        channel_id: uuid.UUID,
        *,
        limit: int = 20,
    ) -> list[JoinRequest]:
        stmt = (
            select(JoinRequest)
            .options(
                selectinload(JoinRequest.telegram_user),
                selectinload(JoinRequest.ai_analyses),
            )
            .where(JoinRequest.channel_id == channel_id)
            .order_by(JoinRequest.created_at.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().unique().all())

    async def get_timeline(self, channel_id: uuid.UUID, *, days: int) -> list[dict[str, Any]]:
        since = datetime.now(UTC) - timedelta(days=days)
        query = text(
            """
            WITH days AS (
                SELECT date_trunc('day', jr.created_at) AS day,
                       COUNT(*) AS total_requests,
                       SUM(CASE WHEN jr.status::text = 'APPROVED' THEN 1 ELSE 0 END) AS approved,
                       SUM(CASE WHEN jr.status::text = 'REJECTED' THEN 1 ELSE 0 END) AS rejected,
                       SUM(CASE WHEN jr.status::text = 'MANUAL_REVIEW' THEN 1 ELSE 0 END) AS manual_review
                FROM join_requests jr
                WHERE jr.channel_id = :channel_id AND jr.created_at >= :since
                GROUP BY 1
            ),
            feedback AS (
                SELECT date_trunc('day', fb.created_at) AS day,
                       COUNT(*) AS feedback_count,
                       SUM(CASE WHEN fb.was_ai_correct THEN 1 ELSE 0 END) AS matched
                FROM ai_feedbacks fb
                JOIN join_requests jr ON jr.id = fb.join_request_id
                WHERE jr.channel_id = :channel_id AND fb.created_at >= :since
                GROUP BY 1
            ),
            ai_calls AS (
                SELECT date_trunc('day', a.created_at) AS day,
                       COUNT(*) AS ai_calls
                FROM ai_analyses a
                JOIN join_requests jr ON jr.id = a.join_request_id
                WHERE jr.channel_id = :channel_id
                  AND a.created_at >= :since
                  AND COALESCE(a.explanation::jsonb->>'ai_status', '') IN ('SUCCESS', 'FALLBACK')
                GROUP BY 1
            ),
            daily_cost AS (
                SELECT date_trunc('day', u.created_at) AS day,
                       COALESCE(AVG(u.estimated_cost), 0) AS avg_cost
                FROM ai_usage u
                WHERE u.created_at >= :since
                GROUP BY 1
            )
            SELECT
                TO_CHAR(COALESCE(d.day, f.day, ac.day), 'YYYY-MM-DD') AS date,
                COALESCE(d.total_requests, 0) AS total_requests,
                COALESCE(d.approved, 0) AS approved,
                COALESCE(d.rejected, 0) AS rejected,
                COALESCE(d.manual_review, 0) AS manual_review,
                COALESCE(f.feedback_count, 0) AS feedback_count,
                CASE
                    WHEN COALESCE(f.feedback_count, 0) > 0
                    THEN ROUND(COALESCE(f.matched, 0)::numeric / f.feedback_count * 100, 2)
                    ELSE NULL
                END AS accuracy_percent,
                COALESCE(ac.ai_calls, 0) AS ai_calls,
                ROUND(
                    COALESCE(ac.ai_calls, 0)::numeric * COALESCE(dc.avg_cost, 0)::numeric,
                    6
                ) AS ai_cost
            FROM days d
            FULL OUTER JOIN feedback f ON d.day = f.day
            FULL OUTER JOIN ai_calls ac ON COALESCE(d.day, f.day) = ac.day
            LEFT JOIN daily_cost dc ON ac.day = dc.day
            ORDER BY date
            """
        )
        rows = (
            await self._session.execute(
                query,
                {"channel_id": channel_id, "since": since},
            )
        ).all()
        return [dict(row._mapping) for row in rows]

    async def get_channel(self, channel_id: uuid.UUID) -> TelegramChannel | None:
        stmt = (
            select(TelegramChannel)
            .options(selectinload(TelegramChannel.bot), selectinload(TelegramChannel.settings))
            .where(TelegramChannel.id == channel_id)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_channels(self) -> list[TelegramChannel]:
        stmt = select(TelegramChannel).order_by(TelegramChannel.created_at.desc())
        return list((await self._session.execute(stmt)).scalars().all())
