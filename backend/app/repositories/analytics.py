import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Float, case, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import JSONB

from app.models.ai_analysis import AIAnalysis
from app.models.ai_feedback import AIFeedback
from app.models.ai_usage import AIUsage
from app.models.enums import AnalysisDecision


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_feedback_accuracy_raw(self) -> dict[str, Any]:
        stmt = select(
            func.count().label("total"),
            func.sum(case((AIFeedback.was_ai_correct.is_(True), 1), else_=0)).label("matched"),
            func.sum(case((AIFeedback.was_ai_correct.is_(False), 1), else_=0)).label("mismatched"),
            func.sum(
                case(
                    (
                        (AIFeedback.ai_decision == AnalysisDecision.APPROVED)
                        & (AIFeedback.human_decision != AnalysisDecision.APPROVED),
                        1,
                    ),
                    else_=0,
                )
            ).label("false_approve"),
            func.sum(
                case(
                    (
                        (AIFeedback.ai_decision == AnalysisDecision.REJECTED)
                        & (AIFeedback.human_decision != AnalysisDecision.REJECTED),
                        1,
                    ),
                    else_=0,
                )
            ).label("false_reject"),
            func.sum(
                case((AIFeedback.ai_decision == AnalysisDecision.MANUAL_REVIEW, 1), else_=0)
            ).label("manual_review_total"),
            func.sum(
                case(
                    (
                        (AIFeedback.ai_decision == AnalysisDecision.MANUAL_REVIEW)
                        & (AIFeedback.was_ai_correct.is_(True)),
                        1,
                    ),
                    else_=0,
                )
            ).label("manual_review_matched"),
        ).select_from(AIFeedback)
        row = (await self._session.execute(stmt)).one()
        return {
            "total": int(row.total or 0),
            "matched": int(row.matched or 0),
            "mismatched": int(row.mismatched or 0),
            "false_approve": int(row.false_approve or 0),
            "false_reject": int(row.false_reject or 0),
            "manual_review_total": int(row.manual_review_total or 0),
            "manual_review_matched": int(row.manual_review_matched or 0),
        }

    async def get_decision_distribution_raw(self) -> list[dict[str, Any]]:
        stmt = (
            select(AIAnalysis.decision, func.count().label("count"))
            .group_by(AIAnalysis.decision)
            .order_by(func.count().desc())
        )
        return [
            {"decision": row.decision.value, "count": int(row.count)}
            for row in (await self._session.execute(stmt)).all()
        ]

    async def get_provider_usage_raw(self) -> list[dict[str, Any]]:
        stmt = (
            select(
                AIUsage.provider,
                AIUsage.model,
                func.count().label("requests"),
                func.coalesce(func.avg(AIUsage.latency_ms), 0.0).label("avg_latency_ms"),
                func.coalesce(func.avg(AIUsage.total_tokens), 0.0).label("avg_tokens"),
                func.coalesce(func.avg(AIUsage.estimated_cost), 0.0).label("avg_cost"),
                func.coalesce(func.sum(AIUsage.estimated_cost), 0.0).label("total_cost"),
            )
            .group_by(AIUsage.provider, AIUsage.model)
            .order_by(func.count().desc())
        )
        return [
            {
                "provider": row.provider,
                "model": row.model,
                "requests": int(row.requests),
                "avg_latency_ms": float(row.avg_latency_ms),
                "avg_tokens": float(row.avg_tokens),
                "avg_cost": float(row.avg_cost),
                "total_cost": float(row.total_cost),
            }
            for row in (await self._session.execute(stmt)).all()
        ]

    async def get_provider_accuracy_raw(self) -> list[dict[str, Any]]:
        explanation_json = cast(AIAnalysis.explanation, JSONB)
        provider_expr = explanation_json["ai_result"]["provider"].astext
        model_expr = explanation_json["ai_result"]["model"].astext
        confidence_expr = cast(explanation_json["ai_result"]["confidence"].astext, Float)

        stmt = (
            select(
                provider_expr.label("provider"),
                model_expr.label("model"),
                func.count().label("requests"),
                func.coalesce(func.avg(confidence_expr), None).label("avg_confidence"),
                func.sum(case((AIFeedback.was_ai_correct.is_(True), 1), else_=0)).label("matched"),
                func.count(AIFeedback.id).label("feedback_count"),
            )
            .select_from(AIAnalysis)
            .join(AIFeedback, AIFeedback.join_request_id == AIAnalysis.join_request_id)
            .where(
                AIAnalysis.explanation.is_not(None),
                explanation_json["ai_result"].is_not(None),
                provider_expr.is_not(None),
                model_expr.is_not(None),
            )
            .group_by(provider_expr, model_expr)
        )
        rows = []
        for row in (await self._session.execute(stmt)).all():
            feedback_count = int(row.feedback_count or 0)
            matched = int(row.matched or 0)
            rows.append(
                {
                    "provider": row.provider or "unknown",
                    "model": row.model or "unknown",
                    "requests": int(row.requests),
                    "avg_confidence": float(row.avg_confidence) if row.avg_confidence is not None else None,
                    "accuracy_percent": round(matched / feedback_count * 100, 2) if feedback_count else None,
                }
            )
        return rows

    async def get_rule_effectiveness_raw(self) -> list[dict[str, Any]]:
        query = text(
            """
            WITH rule_events AS (
                SELECT
                    elem->>'rule' AS rule_name,
                    COALESCE((elem->>'score')::float, 0) AS rule_score,
                    a.decision AS ai_decision,
                    a.join_request_id
                FROM ai_analyses a
                CROSS JOIN LATERAL jsonb_array_elements(
                    CASE
                        WHEN a.explanation IS NOT NULL AND a.explanation LIKE '{%'
                        THEN a.explanation::jsonb->'triggered_rules'
                        ELSE '[]'::jsonb
                    END
                ) AS elem
                WHERE elem->>'rule' IS NOT NULL
            ),
            feedback AS (
                SELECT DISTINCT ON (join_request_id)
                    join_request_id,
                    human_decision,
                    was_ai_correct
                FROM ai_feedbacks
                ORDER BY join_request_id, created_at DESC
            )
            SELECT
                re.rule_name,
                COUNT(*) AS triggered_count,
                COALESCE(AVG(re.rule_score), 0) AS avg_rule_score,
                SUM(CASE WHEN re.ai_decision::text <> 'Approved' THEN 1 ELSE 0 END) AS ai_agreed_count,
                SUM(
                    CASE
                        WHEN f.human_decision::text = 'Rejected' THEN 1
                        WHEN f.human_decision IS NULL THEN 0
                        ELSE 0
                    END
                ) AS admin_agreed_count,
                SUM(
                    CASE
                        WHEN f.human_decision::text = 'Approved'
                             AND re.ai_decision::text <> 'Approved' THEN 1
                        ELSE 0
                    END
                ) AS false_positive_count
            FROM rule_events re
            LEFT JOIN feedback f ON f.join_request_id = re.join_request_id
            GROUP BY re.rule_name
            ORDER BY triggered_count DESC
            """
        )
        rows = (await self._session.execute(query)).all()
        return [
            {
                "rule_name": row.rule_name,
                "triggered_count": int(row.triggered_count),
                "avg_rule_score": float(row.avg_rule_score),
                "ai_agreed_count": int(row.ai_agreed_count or 0),
                "admin_agreed_count": int(row.admin_agreed_count or 0),
                "false_positive_count": int(row.false_positive_count or 0),
            }
            for row in rows
        ]

    async def get_feedback_categories_raw(self) -> dict[str, int]:
        stmt = select(
            func.sum(
                case(
                    (
                        (AIFeedback.ai_decision == AnalysisDecision.REJECTED)
                        & (AIFeedback.human_decision == AnalysisDecision.APPROVED),
                        1,
                    ),
                    else_=0,
                )
            ).label("approve_after_ai_reject"),
            func.sum(
                case(
                    (
                        (AIFeedback.ai_decision == AnalysisDecision.APPROVED)
                        & (AIFeedback.human_decision == AnalysisDecision.REJECTED),
                        1,
                    ),
                    else_=0,
                )
            ).label("reject_after_ai_approve"),
            func.sum(
                case(
                    (
                        (AIFeedback.ai_decision == AnalysisDecision.MANUAL_REVIEW)
                        & (AIFeedback.human_decision == AnalysisDecision.APPROVED),
                        1,
                    ),
                    else_=0,
                )
            ).label("approve_after_manual_review"),
            func.sum(
                case(
                    (
                        (AIFeedback.ai_decision == AnalysisDecision.MANUAL_REVIEW)
                        & (AIFeedback.human_decision == AnalysisDecision.REJECTED),
                        1,
                    ),
                    else_=0,
                )
            ).label("reject_after_manual_review"),
        ).select_from(AIFeedback)
        row = (await self._session.execute(stmt)).one()
        return {
            "approve_after_ai_reject": int(row.approve_after_ai_reject or 0),
            "reject_after_ai_approve": int(row.reject_after_ai_approve or 0),
            "approve_after_manual_review": int(row.approve_after_manual_review or 0),
            "reject_after_manual_review": int(row.reject_after_manual_review or 0),
        }

    async def get_recent_feedback_raw(self, *, limit: int = 50) -> list[dict[str, Any]]:
        stmt = (
            select(AIFeedback)
            .order_by(AIFeedback.created_at.desc())
            .limit(limit)
        )
        items = list((await self._session.execute(stmt)).scalars().all())
        result = []
        for item in items:
            category = self._feedback_category(item.ai_decision, item.human_decision)
            result.append(
                {
                    "id": item.id,
                    "join_request_id": item.join_request_id,
                    "created_at": item.created_at,
                    "ai_decision": item.ai_decision.value,
                    "human_decision": item.human_decision.value,
                    "was_ai_correct": item.was_ai_correct,
                    "category": category,
                }
            )
        return result

    async def get_timeline_raw(self, *, days: int) -> list[dict[str, Any]]:
        since = datetime.now(UTC) - timedelta(days=days)
        day_expr = func.date_trunc("day", AIFeedback.created_at)

        feedback_stmt = (
            select(
                day_expr.label("day"),
                func.count().label("feedback_count"),
                func.sum(case((AIFeedback.was_ai_correct.is_(True), 1), else_=0)).label("matched"),
            )
            .where(AIFeedback.created_at >= since)
            .group_by(day_expr)
        )
        feedback_by_day = {
            row.day.date().isoformat(): {
                "feedback_count": int(row.feedback_count),
                "matched": int(row.matched or 0),
            }
            for row in (await self._session.execute(feedback_stmt)).all()
            if row.day
        }

        usage_day_expr = func.date_trunc("day", AIUsage.created_at)
        usage_stmt = (
            select(
                usage_day_expr.label("day"),
                func.count().label("usage_count"),
                func.coalesce(func.avg(AIUsage.estimated_cost), 0.0).label("avg_cost"),
                func.coalesce(func.avg(AIUsage.latency_ms), 0.0).label("avg_latency_ms"),
            )
            .where(AIUsage.created_at >= since)
            .group_by(usage_day_expr)
        )
        usage_by_day = {
            row.day.date().isoformat(): {
                "usage_count": int(row.usage_count),
                "avg_cost": float(row.avg_cost),
                "avg_latency_ms": float(row.avg_latency_ms),
            }
            for row in (await self._session.execute(usage_stmt)).all()
            if row.day
        }

        explanation_json = cast(AIAnalysis.explanation, JSONB)
        confidence_expr = cast(explanation_json["ai_result"]["confidence"].astext, Float)
        analysis_day_expr = func.date_trunc("day", AIAnalysis.created_at)
        analysis_stmt = (
            select(
                analysis_day_expr.label("day"),
                func.coalesce(func.avg(confidence_expr), None).label("avg_confidence"),
            )
            .where(
                AIAnalysis.created_at >= since,
                AIAnalysis.explanation.is_not(None),
                explanation_json["ai_result"].is_not(None),
            )
            .group_by(analysis_day_expr)
        )
        confidence_by_day = {
            row.day.date().isoformat(): float(row.avg_confidence)
            if row.avg_confidence is not None
            else None
            for row in (await self._session.execute(analysis_stmt)).all()
            if row.day
        }

        all_days = sorted(set(feedback_by_day) | set(usage_by_day) | set(confidence_by_day))
        timeline = []
        for day in all_days:
            fb = feedback_by_day.get(day, {"feedback_count": 0, "matched": 0})
            usage = usage_by_day.get(day, {"usage_count": 0, "avg_cost": 0.0, "avg_latency_ms": 0.0})
            feedback_count = fb["feedback_count"]
            accuracy = (
                round(fb["matched"] / feedback_count * 100, 2) if feedback_count else None
            )
            timeline.append(
                {
                    "date": day,
                    "accuracy_percent": accuracy,
                    "avg_cost": usage["avg_cost"],
                    "avg_latency_ms": usage["avg_latency_ms"],
                    "avg_confidence": confidence_by_day.get(day),
                    "feedback_count": feedback_count,
                    "usage_count": usage["usage_count"],
                }
            )
        return timeline

    async def get_usage_cost_raw(self) -> dict[str, float]:
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        totals = (
            await self._session.execute(
                select(
                    func.coalesce(func.sum(AIUsage.estimated_cost), 0.0),
                    func.coalesce(func.avg(AIUsage.total_tokens), 0.0),
                    func.coalesce(func.avg(AIUsage.latency_ms), 0.0),
                )
            )
        ).one()

        today_cost = (
            await self._session.execute(
                select(func.coalesce(func.sum(AIUsage.estimated_cost), 0.0)).where(
                    AIUsage.created_at >= today_start
                )
            )
        ).scalar_one()

        month_cost = (
            await self._session.execute(
                select(func.coalesce(func.sum(AIUsage.estimated_cost), 0.0)).where(
                    AIUsage.created_at >= month_start
                )
            )
        ).scalar_one()

        return {
            "total_cost": float(totals[0] or 0.0),
            "today_cost": float(today_cost or 0.0),
            "month_cost": float(month_cost or 0.0),
            "avg_tokens": float(totals[1] or 0.0),
            "avg_latency_ms": float(totals[2] or 0.0),
        }

    async def get_model_rankings_raw(self) -> dict[str, str | None]:
        usage_stmt = (
            select(
                AIUsage.model,
                func.count().label("requests"),
                func.coalesce(func.sum(AIUsage.estimated_cost), 0.0).label("total_cost"),
            )
            .group_by(AIUsage.model)
        )
        usage_rows = (await self._session.execute(usage_stmt)).all()
        most_used = max(usage_rows, key=lambda row: row.requests, default=None)
        most_expensive = max(usage_rows, key=lambda row: row.total_cost, default=None)

        explanation_json = cast(AIAnalysis.explanation, JSONB)
        model_expr = explanation_json["ai_result"]["model"].astext
        accuracy_stmt = (
            select(
                model_expr.label("model"),
                func.sum(case((AIFeedback.was_ai_correct.is_(True), 1), else_=0)).label("matched"),
                func.count(AIFeedback.id).label("total"),
            )
            .select_from(AIAnalysis)
            .join(AIFeedback, AIFeedback.join_request_id == AIAnalysis.join_request_id)
            .where(explanation_json["ai_result"].is_not(None), model_expr.is_not(None))
            .group_by(model_expr)
        )
        accuracy_rows = (await self._session.execute(accuracy_stmt)).all()
        best_model = None
        best_accuracy = -1.0
        for row in accuracy_rows:
            total = int(row.total or 0)
            if total == 0:
                continue
            accuracy = int(row.matched or 0) / total
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_model = row.model

        return {
            "most_used_model": most_used.model if most_used else None,
            "most_expensive_model": most_expensive.model if most_expensive else None,
            "most_accurate_model": best_model,
        }

    async def get_latest_feedback_for_request(
        self,
        join_request_id: uuid.UUID,
    ) -> AIFeedback | None:
        stmt = (
            select(AIFeedback)
            .where(AIFeedback.join_request_id == join_request_id)
            .order_by(AIFeedback.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _feedback_category(
        ai_decision: AnalysisDecision,
        human_decision: AnalysisDecision,
    ) -> str:
        if ai_decision == AnalysisDecision.REJECTED and human_decision == AnalysisDecision.APPROVED:
            return "approve_after_ai_reject"
        if ai_decision == AnalysisDecision.APPROVED and human_decision == AnalysisDecision.REJECTED:
            return "reject_after_ai_approve"
        if ai_decision == AnalysisDecision.MANUAL_REVIEW and human_decision == AnalysisDecision.APPROVED:
            return "approve_after_manual_review"
        if ai_decision == AnalysisDecision.MANUAL_REVIEW and human_decision == AnalysisDecision.REJECTED:
            return "reject_after_manual_review"
        return "other"
