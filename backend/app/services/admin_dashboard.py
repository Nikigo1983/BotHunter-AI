import json
import math
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.features import FeatureExtractor
from app.models.enums import JoinRequestStatus
from app.explainability import HybridExplainabilityBuilder
from app.repositories.admin_dashboard import AdminDashboardRepository, StatusFilter
from app.repositories.deps import (
    get_admin_dashboard_repository,
    get_ai_feedback_repository,
    get_blacklist_repository,
    get_manual_review_repository,
    get_reputation_history_repository,
    get_whitelist_repository,
)
from app.services.analytics import AnalyticsService
from app.reputation.engine import DEFAULT_TRUST_SCORE
from app.reputation.service import ReputationService
from app.schemas.admin_dashboard import (
    AIFeedbackItemDTO,
    AIInfoDTO,
    DashboardStatisticsDTO,
    ExplainableAIDTO,
    HistoryDTO,
    JoinRequestDetailDTO,
    JoinRequestListItemDTO,
    JoinRequestListResultDTO,
    ManualReviewItemDTO,
    ReputationHistoryItemDTO,
    RiskProfileDTO,
    RuleInfoDTO,
    UserInfoDTO,
)

PAGE_SIZE = 25

TELEGRAM_ACTION_MAP = {
    JoinRequestStatus.APPROVED: "approved",
    JoinRequestStatus.REJECTED: "declined",
    JoinRequestStatus.MANUAL_REVIEW: "left_pending",
    JoinRequestStatus.PENDING: "pending",
}

FINAL_STATUSES = {JoinRequestStatus.APPROVED, JoinRequestStatus.REJECTED}


class AdminDashboardService:
    def __init__(
        self,
        session: AsyncSession,
        repository: AdminDashboardRepository | None = None,
        feature_extractor: FeatureExtractor | None = None,
    ) -> None:
        self._session = session
        self._repository = repository or get_admin_dashboard_repository(session)
        self._feature_extractor = feature_extractor or FeatureExtractor()
        self._manual_review_repo = get_manual_review_repository(session)
        self._ai_feedback_repo = get_ai_feedback_repository(session)
        self._whitelist_repo = get_whitelist_repository(session)
        self._blacklist_repo = get_blacklist_repository(session)
        self._reputation_service = ReputationService(session)
        self._reputation_history_repo = get_reputation_history_repository(session)

    async def list_join_requests(
        self,
        *,
        status_filter: StatusFilter = "all",
        search: str | None = None,
        page: int = 1,
        page_size: int = PAGE_SIZE,
    ) -> JoinRequestListResultDTO:
        safe_page = max(page, 1)
        offset = (safe_page - 1) * page_size
        result = await self._repository.list_join_requests(
            status_filter=status_filter,
            search=search,
            offset=offset,
            limit=page_size,
        )
        total_pages = max(1, math.ceil(result.total / page_size)) if result.total else 1
        user_ids = [row.telegram_user.id for row in result.rows]
        list_flags = await self._repository.get_user_list_flags(user_ids)
        trust_scores = await self._repository.get_trust_scores(user_ids)
        items = [self._map_list_item(row, list_flags, trust_scores) for row in result.rows]
        return JoinRequestListResultDTO(
            items=items,
            total=result.total,
            page=safe_page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_join_request_detail(
        self,
        join_request_id: uuid.UUID,
    ) -> JoinRequestDetailDTO | None:
        row = await self._repository.get_join_request(join_request_id)
        if row is None:
            return None

        explanation_payload = self._parse_explanation(row.analysis.explanation if row.analysis else None)
        feature_set = self._feature_extractor.extract(row.telegram_user).to_dict()
        feature_set["system"]["extracted_at"] = str(feature_set["system"]["extracted_at"])

        risk_data = explanation_payload.get("risk_profile", {})
        ai_result = explanation_payload.get("ai_result")

        is_whitelisted = await self._whitelist_repo.exists_by_telegram_user_id(row.telegram_user.id)
        is_blacklisted = await self._blacklist_repo.exists_by_telegram_user_id(row.telegram_user.id)
        manual_reviews = await self._manual_review_repo.list_by_join_request_id(join_request_id)
        ai_feedbacks = await self._ai_feedback_repo.list_by_join_request_id(join_request_id)
        trust_score = await self._reputation_service.get_score(row.telegram_user.id)
        reputation_history = await self._reputation_history_repo.list_by_telegram_user_id(
            row.telegram_user.id
        )
        decision_comparison = await AnalyticsService(self._session).build_decision_comparison(
            join_request_id
        )

        return JoinRequestDetailDTO(
            id=row.join_request.id,
            channel_title=row.channel.title,
            status=row.join_request.status,
            user=UserInfoDTO(
                telegram_id=row.telegram_user.telegram_id,
                username=row.telegram_user.username,
                first_name=row.telegram_user.first_name,
                last_name=row.telegram_user.last_name,
                language_code=row.telegram_user.language_code,
                is_premium=row.telegram_user.is_premium,
                has_photo=row.telegram_user.has_photo,
            ),
            feature_set=feature_set,
            rules=RuleInfoDTO(
                rule_score=row.analysis.rule_score if row.analysis else None,
                triggered_rules=explanation_payload.get("triggered_rules", []),
            ),
            risk_profile=RiskProfileDTO(
                risk_level=risk_data.get("risk_level"),
                confidence=risk_data.get("confidence"),
                signals=list(risk_data.get("signals", [])),
                summary=risk_data.get("summary"),
                main_reason=risk_data.get("main_reason"),
                trust_score=risk_data.get("trust_score", trust_score),
            ),
            ai=AIInfoDTO(
                ai_status=explanation_payload.get("ai_status"),
                ai_score=row.analysis.ai_score if row.analysis else None,
                decision=row.analysis.decision if row.analysis else None,
                explanation=row.analysis.explanation if row.analysis else None,
                ai_result=ai_result,
                explainable=self._build_explainable(
                    ai_result=ai_result,
                    ai_score=row.analysis.ai_score if row.analysis else None,
                    decision=row.analysis.decision.value if row.analysis and row.analysis.decision else None,
                    ai_status=explanation_payload.get("ai_status"),
                    feature_set=feature_set,
                    trust_score=trust_score,
                    triggered_rules=explanation_payload.get("triggered_rules", []),
                    rule_score=row.analysis.rule_score if row.analysis else None,
                ),
            ),
            history=HistoryDTO(
                created_at=row.join_request.created_at,
                decision_at=row.analysis.created_at if row.analysis else None,
                telegram_action=TELEGRAM_ACTION_MAP.get(row.join_request.status, "unknown"),
            ),
            rule_score=row.analysis.rule_score if row.analysis else None,
            ai_score=row.analysis.ai_score if row.analysis else None,
            final_score=row.analysis.final_score if row.analysis else None,
            is_whitelisted=is_whitelisted,
            is_blacklisted=is_blacklisted,
            actions_disabled=row.join_request.status in FINAL_STATUSES,
            manual_reviews=[
                ManualReviewItemDTO(
                    admin_action=item.admin_action.value,
                    previous_decision=item.previous_decision.value,
                    final_decision=item.final_decision.value,
                    created_at=item.created_at,
                    comment=item.comment,
                )
                for item in manual_reviews
            ],
            ai_feedbacks=[
                AIFeedbackItemDTO(
                    rule_score=item.rule_score,
                    ai_score=item.ai_score,
                    ai_decision=item.ai_decision.value,
                    human_decision=item.human_decision.value,
                    was_ai_correct=item.was_ai_correct,
                    created_at=item.created_at,
                )
                for item in ai_feedbacks
            ],
            trust_score=trust_score,
            reputation_history=[
                ReputationHistoryItemDTO(
                    created_at=item.created_at,
                    old_score=item.old_score,
                    new_score=item.new_score,
                    reason=item.reason.value,
                    actor=item.actor,
                )
                for item in reputation_history
            ],
            decision_comparison=decision_comparison,
        )

    async def get_statistics(self) -> DashboardStatisticsDTO:
        raw = await self._repository.get_statistics()
        return DashboardStatisticsDTO(
            total=int(raw["total"]),
            approved=int(raw["approved"]),
            rejected=int(raw["rejected"]),
            manual_review=int(raw["manual_review"]),
            pending=int(raw["pending"]),
            avg_rule_score=raw["avg_rule_score"],
            avg_ai_score=raw["avg_ai_score"],
            avg_trust_score=raw["avg_trust_score"],
        )

    async def get_reputation_detail(self, telegram_id: int):
        from app.repositories.deps import get_telegram_user_repository

        user = await get_telegram_user_repository(self._session).get_by_telegram_id(telegram_id)
        if user is None:
            return None

        history = await self._reputation_history_repo.list_by_telegram_user_id(user.id)
        current_score = await self._reputation_service.get_score(user.id)
        trend = ReputationService.calculate_trend(history)
        return {
            "telegram_id": telegram_id,
            "current_score": current_score,
            "history": history,
            "trend": trend,
        }

    @staticmethod
    def _map_list_item(
        row,
        list_flags: dict | None = None,
        trust_scores: dict | None = None,
    ) -> JoinRequestListItemDTO:
        analysis = row.analysis
        whitelisted, blacklisted = (False, False)
        if list_flags is not None:
            whitelisted, blacklisted = list_flags.get(row.telegram_user.id, (False, False))
        trust_score = DEFAULT_TRUST_SCORE
        if trust_scores is not None:
            trust_score = trust_scores.get(row.telegram_user.id, DEFAULT_TRUST_SCORE)
        return JoinRequestListItemDTO(
            id=row.join_request.id,
            created_at=row.join_request.created_at,
            channel_title=row.channel.title,
            telegram_id=row.telegram_user.telegram_id,
            username=row.telegram_user.username,
            rule_score=analysis.rule_score if analysis else None,
            ai_score=analysis.ai_score if analysis else None,
            final_score=analysis.final_score if analysis else None,
            decision=analysis.decision if analysis else None,
            status=row.join_request.status,
            is_whitelisted=whitelisted,
            is_blacklisted=blacklisted,
            trust_score=trust_score,
        )

    @staticmethod
    def _build_explainable(
        *,
        ai_result: dict[str, Any] | None,
        ai_score: float | None,
        decision: str | None,
        ai_status: str | None,
        feature_set: dict[str, Any],
        trust_score: float,
        triggered_rules: list[dict[str, Any]],
        rule_score: float | None,
    ) -> ExplainableAIDTO | None:
        payload = ai_result or {}
        ai_positive = list(payload.get("positive_signals") or [])
        ai_negative = list(payload.get("negative_signals") or [])
        legacy_signals = payload.get("signals") or []
        if legacy_signals and not ai_positive and not ai_negative:
            ai_negative = list(legacy_signals)

        hybrid = HybridExplainabilityBuilder.build(
            feature_set=feature_set,
            trust_score=trust_score,
            triggered_rules=triggered_rules,
            rule_score=rule_score,
            ai_positive=ai_positive,
            ai_negative=ai_negative,
        )

        has_ai_payload = ai_result is not None or ai_score is not None or decision is not None
        has_hybrid_signals = bool(hybrid.positive_signals or hybrid.negative_signals)
        if not has_ai_payload and not has_hybrid_signals:
            return None

        resolved_decision = payload.get("decision") or decision
        resolved_score = payload.get("ai_score", payload.get("risk_score", ai_score))
        risk_score = float(resolved_score) if resolved_score is not None else None

        return ExplainableAIDTO(
            risk_score=risk_score,
            decision=str(resolved_decision) if resolved_decision is not None else None,
            confidence=payload.get("confidence"),
            reason=payload.get("reason"),
            recommended_action=payload.get("recommended_action"),
            positive_signals=hybrid.positive_signals,
            negative_signals=hybrid.negative_signals,
            short_summary=payload.get("short_summary"),
            provider=payload.get("provider"),
            model=payload.get("model"),
            risk_level=HybridExplainabilityBuilder.risk_level(risk_score),
            risk_level_label=HybridExplainabilityBuilder.risk_level_label(risk_score),
        )

    @staticmethod
    def _parse_explanation(raw_explanation: str | None) -> dict[str, Any]:
        if not raw_explanation:
            return {}
        try:
            payload = json.loads(raw_explanation)
        except json.JSONDecodeError:
            return {"triggered_rules": [], "legacy_explanation": raw_explanation}
        if isinstance(payload, list):
            return {"triggered_rules": payload}
        if isinstance(payload, dict):
            return payload
        return {}
