from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.analytics import AnalyticsRepository
from app.repositories.deps import get_analytics_repository
from app.schemas.analytics import (
    AIAccuracyDTO,
    AnalyticsOverviewDTO,
    DecisionComparisonDTO,
    DecisionDistributionItemDTO,
    FeedbackCaseDTO,
    FeedbackCategoryDTO,
    ProviderStatDTO,
    RuleEffectivenessDTO,
    TimelinePointDTO,
    UsageDashboardDTO,
)

FEEDBACK_CATEGORY_LABELS = {
    "approve_after_ai_reject": "Approve after AI Reject",
    "reject_after_ai_approve": "Reject after AI Approve",
    "approve_after_manual_review": "Approve after Manual Review",
    "reject_after_manual_review": "Reject after Manual Review",
}


class AnalyticsService:
    def __init__(
        self,
        session: AsyncSession,
        repository: AnalyticsRepository | None = None,
        tenant=None,
    ) -> None:
        self._session = session
        if repository is not None:
            self._repository = repository
        elif tenant is not None:
            self._repository = get_analytics_repository(
                session,
                organization_id=tenant.organization_id,
                workspace_id=tenant.workspace_id,
            )
        else:
            self._repository = get_analytics_repository(session)

    async def get_overview(self) -> AnalyticsOverviewDTO:
        return AnalyticsOverviewDTO(
            accuracy=await self.get_accuracy(),
            decision_distribution=await self.get_decision_distribution(),
            providers=await self.get_provider_statistics(),
            rules=await self.get_rule_effectiveness(),
            feedback_categories=await self.get_feedback_categories(),
            recent_feedback=await self.get_recent_feedback(limit=50),
            usage=await self.get_usage_dashboard(),
        )

    async def get_accuracy(self) -> AIAccuracyDTO:
        raw = await self._repository.get_feedback_accuracy_raw()
        total = raw["total"]
        matched = raw["matched"]
        manual_total = raw["manual_review_total"]
        manual_matched = raw["manual_review_matched"]
        return AIAccuracyDTO(
            total_decisions=total,
            matched=matched,
            mismatched=raw["mismatched"],
            accuracy_percent=round(matched / total * 100, 2) if total else None,
            false_approve=raw["false_approve"],
            false_reject=raw["false_reject"],
            manual_review_accuracy_percent=(
                round(manual_matched / manual_total * 100, 2) if manual_total else None
            ),
        )

    async def get_decision_distribution(self) -> list[DecisionDistributionItemDTO]:
        rows = await self._repository.get_decision_distribution_raw()
        return [DecisionDistributionItemDTO(decision=row["decision"], count=row["count"]) for row in rows]

    async def get_provider_statistics(self) -> list[ProviderStatDTO]:
        usage_rows = await self._repository.get_provider_usage_raw()
        accuracy_map = {
            (row["provider"], row["model"]): row
            for row in await self._repository.get_provider_accuracy_raw()
        }
        providers: list[ProviderStatDTO] = []
        for row in usage_rows:
            key = (row["provider"], row["model"])
            accuracy_row = accuracy_map.get(key, {})
            providers.append(
                ProviderStatDTO(
                    provider=row["provider"],
                    model=row["model"],
                    requests=row["requests"],
                    avg_latency_ms=round(row["avg_latency_ms"], 2),
                    avg_tokens=round(row["avg_tokens"], 2),
                    avg_cost=round(row["avg_cost"], 6),
                    avg_confidence=accuracy_row.get("avg_confidence"),
                    accuracy_percent=accuracy_row.get("accuracy_percent"),
                )
            )
        return providers

    async def get_rule_effectiveness(self) -> list[RuleEffectivenessDTO]:
        rows = await self._repository.get_rule_effectiveness_raw()
        return [
            RuleEffectivenessDTO(
                rule_name=row["rule_name"],
                triggered_count=row["triggered_count"],
                avg_rule_score=round(row["avg_rule_score"], 2),
                ai_agreed_count=row["ai_agreed_count"],
                admin_agreed_count=row["admin_agreed_count"],
                false_positive_count=row["false_positive_count"],
            )
            for row in rows
        ]

    async def get_feedback_categories(self) -> list[FeedbackCategoryDTO]:
        raw = await self._repository.get_feedback_categories_raw()
        return [
            FeedbackCategoryDTO(
                category=category,
                label=FEEDBACK_CATEGORY_LABELS[category],
                count=count,
            )
            for category, count in raw.items()
        ]

    async def get_recent_feedback(self, *, limit: int = 50) -> list[FeedbackCaseDTO]:
        rows = await self._repository.get_recent_feedback_raw(limit=limit)
        return [
            FeedbackCaseDTO(
                id=row["id"],
                join_request_id=row["join_request_id"],
                created_at=row["created_at"],
                ai_decision=row["ai_decision"],
                human_decision=row["human_decision"],
                was_ai_correct=row["was_ai_correct"],
                category=row["category"],
            )
            for row in rows
        ]

    async def get_timeline(self, *, days: int = 30) -> list[TimelinePointDTO]:
        safe_days = days if days in {7, 30, 90} else 30
        rows = await self._repository.get_timeline_raw(days=safe_days)
        return [
            TimelinePointDTO(
                date=row["date"],
                accuracy_percent=row["accuracy_percent"],
                avg_cost=round(row["avg_cost"], 6),
                avg_latency_ms=round(row["avg_latency_ms"], 2),
                avg_confidence=(
                    round(row["avg_confidence"], 2) if row["avg_confidence"] is not None else None
                ),
                feedback_count=row["feedback_count"],
                usage_count=row["usage_count"],
            )
            for row in rows
        ]

    async def get_usage_dashboard(self) -> UsageDashboardDTO:
        costs = await self._repository.get_usage_cost_raw()
        rankings = await self._repository.get_model_rankings_raw()
        return UsageDashboardDTO(
            total_cost=round(costs["total_cost"], 6),
            today_cost=round(costs["today_cost"], 6),
            month_cost=round(costs["month_cost"], 6),
            avg_tokens=round(costs["avg_tokens"], 2),
            avg_latency_ms=round(costs["avg_latency_ms"], 2),
            most_used_model=rankings["most_used_model"],
            most_accurate_model=rankings["most_accurate_model"],
            most_expensive_model=rankings["most_expensive_model"],
        )

    async def build_decision_comparison(self, join_request_id) -> DecisionComparisonDTO | None:
        feedback = await self._repository.get_latest_feedback_for_request(join_request_id)
        if feedback is None:
            return None

        has_override = feedback.ai_decision != feedback.human_decision
        if not has_override:
            verdict = "AI подтвердился"
            verdict_class = "success"
        else:
            verdict = "AI ошибся"
            verdict_class = "danger"

        return DecisionComparisonDTO(
            ai_decision=feedback.ai_decision.value,
            human_decision=feedback.human_decision.value,
            was_ai_correct=feedback.was_ai_correct,
            has_override=has_override,
            verdict=verdict,
            verdict_class=verdict_class,
        )
