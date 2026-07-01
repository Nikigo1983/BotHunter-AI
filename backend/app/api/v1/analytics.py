from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.deps import require_api_dashboard_auth
from app.database.session import get_db_session
from app.schemas.analytics import (
    AIAccuracyResponse,
    AnalyticsOverviewResponse,
    DecisionDistributionItemResponse,
    FeedbackCaseResponse,
    FeedbackCategoryResponse,
    ProviderStatResponse,
    RuleEffectivenessResponse,
    TimelinePointResponse,
    UsageDashboardResponse,
)
from app.services.analytics import AnalyticsService

router = APIRouter(
    prefix="/admin/analytics",
    tags=["admin-analytics"],
    dependencies=[Depends(require_api_dashboard_auth)],
)


async def get_analytics_service(
    session: AsyncSession = Depends(get_db_session),
) -> AnalyticsService:
    return AnalyticsService(session)


def _map_accuracy(service_result):
    return AIAccuracyResponse(
        total_decisions=service_result.total_decisions,
        matched=service_result.matched,
        mismatched=service_result.mismatched,
        accuracy_percent=service_result.accuracy_percent,
        false_approve=service_result.false_approve,
        false_reject=service_result.false_reject,
        manual_review_accuracy_percent=service_result.manual_review_accuracy_percent,
    )


@router.get("", response_model=AnalyticsOverviewResponse)
async def get_analytics_overview(
    service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsOverviewResponse:
    overview = await service.get_overview()
    return AnalyticsOverviewResponse(
        accuracy=_map_accuracy(overview.accuracy),
        decision_distribution=[
            DecisionDistributionItemResponse(decision=item.decision, count=item.count)
            for item in overview.decision_distribution
        ],
        providers=[
            ProviderStatResponse(
                provider=item.provider,
                model=item.model,
                requests=item.requests,
                avg_latency_ms=item.avg_latency_ms,
                avg_tokens=item.avg_tokens,
                avg_cost=item.avg_cost,
                avg_confidence=item.avg_confidence,
                accuracy_percent=item.accuracy_percent,
            )
            for item in overview.providers
        ],
        rules=[
            RuleEffectivenessResponse(
                rule_name=item.rule_name,
                triggered_count=item.triggered_count,
                avg_rule_score=item.avg_rule_score,
                ai_agreed_count=item.ai_agreed_count,
                admin_agreed_count=item.admin_agreed_count,
                false_positive_count=item.false_positive_count,
            )
            for item in overview.rules
        ],
        feedback_categories=[
            FeedbackCategoryResponse(
                category=item.category,
                label=item.label,
                count=item.count,
            )
            for item in overview.feedback_categories
        ],
        recent_feedback=[
            FeedbackCaseResponse(
                id=item.id,
                join_request_id=item.join_request_id,
                created_at=item.created_at,
                ai_decision=item.ai_decision,
                human_decision=item.human_decision,
                was_ai_correct=item.was_ai_correct,
                category=item.category,
            )
            for item in overview.recent_feedback
        ],
        usage=UsageDashboardResponse(
            total_cost=overview.usage.total_cost,
            today_cost=overview.usage.today_cost,
            month_cost=overview.usage.month_cost,
            avg_tokens=overview.usage.avg_tokens,
            avg_latency_ms=overview.usage.avg_latency_ms,
            most_used_model=overview.usage.most_used_model,
            most_accurate_model=overview.usage.most_accurate_model,
            most_expensive_model=overview.usage.most_expensive_model,
        ),
    )


@router.get("/accuracy", response_model=AIAccuracyResponse)
async def get_analytics_accuracy(
    service: AnalyticsService = Depends(get_analytics_service),
) -> AIAccuracyResponse:
    return _map_accuracy(await service.get_accuracy())


@router.get("/rules", response_model=list[RuleEffectivenessResponse])
async def get_analytics_rules(
    service: AnalyticsService = Depends(get_analytics_service),
) -> list[RuleEffectivenessResponse]:
    rules = await service.get_rule_effectiveness()
    return [
        RuleEffectivenessResponse(
            rule_name=item.rule_name,
            triggered_count=item.triggered_count,
            avg_rule_score=item.avg_rule_score,
            ai_agreed_count=item.ai_agreed_count,
            admin_agreed_count=item.admin_agreed_count,
            false_positive_count=item.false_positive_count,
        )
        for item in rules
    ]


@router.get("/providers", response_model=list[ProviderStatResponse])
async def get_analytics_providers(
    service: AnalyticsService = Depends(get_analytics_service),
) -> list[ProviderStatResponse]:
    providers = await service.get_provider_statistics()
    return [
        ProviderStatResponse(
            provider=item.provider,
            model=item.model,
            requests=item.requests,
            avg_latency_ms=item.avg_latency_ms,
            avg_tokens=item.avg_tokens,
            avg_cost=item.avg_cost,
            avg_confidence=item.avg_confidence,
            accuracy_percent=item.accuracy_percent,
        )
        for item in providers
    ]


@router.get("/timeline", response_model=list[TimelinePointResponse])
async def get_analytics_timeline(
    days: int = Query(default=30, ge=7, le=90),
    service: AnalyticsService = Depends(get_analytics_service),
) -> list[TimelinePointResponse]:
    timeline = await service.get_timeline(days=days)
    return [
        TimelinePointResponse(
            date=item.date,
            accuracy_percent=item.accuracy_percent,
            avg_cost=item.avg_cost,
            avg_latency_ms=item.avg_latency_ms,
            avg_confidence=item.avg_confidence,
            feedback_count=item.feedback_count,
            usage_count=item.usage_count,
        )
        for item in timeline
    ]
