import json
import math
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.enums import AIServiceStatus
from app.ai.prompt_builder import PromptBuilder
from app.ai.service import AIService
from app.features import FeatureExtractor
from app.investigation.export import export_case_json, export_case_pdf, sanitize_payload
from app.investigation.rule_inspector import RuleInspector
from app.investigation.timeline_builder import TimelineBuilder
from app.models.audit_log import AuditLog
from app.models.enums import AnalysisDecision, JoinRequestStatus
from app.repositories.deps import (
    get_audit_log_repository,
    get_investigation_repository,
    get_manual_review_repository,
)
from app.repositories.investigation import InvestigationFilters, InvestigationStatusFilter, STATUS_FILTER_MAP
from app.reputation.service import ReputationService
from app.risk import RiskProfileBuilder
from app.rules.engine import RuleEngine
from app.schemas.investigation import (
    AIResponseViewDTO,
    AuditLogItemDTO,
    DecisionFlowDTO,
    InvestigationDetailDTO,
    InvestigationListItemDTO,
    InvestigationListResultDTO,
    PromptViewDTO,
    ReplayResultDTO,
    RuleInspectionItemDTO,
)
from app.services.admin_dashboard import AdminDashboardService, PAGE_SIZE, TELEGRAM_ACTION_MAP
from app.services.decision_engine import DecisionEngine
from app.services.join_request_processing import JoinRequestProcessingService
from app.services.policy import PolicyService


class InvestigationService:
    ACTOR = "admin_dashboard"

    def __init__(
        self,
        session: AsyncSession,
        *,
        ai_service: AIService | None = None,
    ) -> None:
        self._session = session
        self._repo = get_investigation_repository(session)
        self._audit_repo = get_audit_log_repository(session)
        self._manual_review_repo = get_manual_review_repository(session)
        self._dashboard = AdminDashboardService(session)
        self._reputation_service = ReputationService(session)
        self._feature_extractor = FeatureExtractor()
        self._rule_engine = RuleEngine()
        self._decision_engine = DecisionEngine()
        self._risk_profile_builder = RiskProfileBuilder(thresholds=self._decision_engine.thresholds)
        self._prompt_builder = PromptBuilder()
        self._rule_inspector = RuleInspector()
        self._ai_service = ai_service or AIService()

    async def list_investigations(
        self,
        *,
        filters: InvestigationFilters,
        page: int = 1,
        page_size: int = PAGE_SIZE,
    ) -> InvestigationListResultDTO:
        safe_page = max(page, 1)
        offset = (safe_page - 1) * page_size
        result = await self._repo.list_investigations(
            filters=filters,
            offset=offset,
            limit=page_size,
        )
        total_pages = max(1, math.ceil(result.total / page_size)) if result.total else 1
        items: list[InvestigationListItemDTO] = []
        for row in result.rows:
            feedback = await self._repo.get_latest_feedback(row.join_request.id)
            trust_score = await self._reputation_service.get_score(row.telegram_user.id)
            analysis = row.analysis
            items.append(
                InvestigationListItemDTO(
                    id=row.join_request.id,
                    created_at=row.join_request.created_at,
                    channel_id=row.channel.id,
                    channel_title=row.channel.title,
                    telegram_id=row.telegram_user.telegram_id,
                    username=row.telegram_user.username,
                    first_name=row.telegram_user.first_name,
                    last_name=row.telegram_user.last_name,
                    status=row.join_request.status,
                    rule_score=analysis.rule_score if analysis else None,
                    ai_score=analysis.ai_score if analysis else None,
                    final_score=analysis.final_score if analysis else None,
                    ai_decision=analysis.decision.value if analysis and analysis.decision else None,
                    human_decision=feedback.human_decision.value if feedback else None,
                    trust_score=trust_score,
                )
            )
        return InvestigationListResultDTO(
            items=items,
            total=result.total,
            page=safe_page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_investigation_detail(
        self,
        join_request_id: uuid.UUID,
    ) -> InvestigationDetailDTO | None:
        row = await self._repo.get_investigation(join_request_id)
        if row is None:
            return None

        case = await self._dashboard.get_join_request_detail(join_request_id)
        if case is None:
            return None

        explanation = AdminDashboardService._parse_explanation(
            row.analysis.explanation if row.analysis else None
        )
        manual_reviews = await self._manual_review_repo.list_by_join_request_id(join_request_id)
        audit_logs = await self._repo.list_audit_logs(join_request_id)
        feedback = await self._repo.get_latest_feedback(join_request_id)

        features = self._feature_extractor.extract(row.telegram_user)
        rule_inspection = self._rule_inspector.inspect(features)
        rule_engine_decision = None
        if row.analysis and row.analysis.rule_score is not None:
            rule_engine_decision = self._decision_engine.decide(int(row.analysis.rule_score))

        timeline = TimelineBuilder.build(
            created_at=row.join_request.created_at,
            analysis_created_at=row.analysis.created_at if row.analysis else None,
            explanation=explanation,
            analysis_decision=row.analysis.decision if row.analysis else None,
            rule_score=row.analysis.rule_score if row.analysis else None,
            join_status=row.join_request.status,
            telegram_action=TELEGRAM_ACTION_MAP.get(row.join_request.status, "unknown"),
            manual_reviews=manual_reviews,
            audit_logs=audit_logs,
            rule_engine_decision=rule_engine_decision,
            ai_status=explanation.get("ai_status"),
        )

        prompt = self._build_prompt_view(row, explanation)
        ai_response = self._build_ai_response_view(explanation, row.analysis.explanation if row.analysis else None)
        decision_flow = self._build_decision_flow(
            rule_engine_decision=rule_engine_decision,
            analysis=row.analysis,
            explanation=explanation,
            feedback=feedback,
            join_status=row.join_request.status,
        )

        return InvestigationDetailDTO(
            case=case,
            channel_id=row.channel.id,
            timeline=[
                self._map_timeline_event(item) for item in timeline
            ],
            prompt=prompt,
            ai_response=ai_response,
            rule_inspection=[
                RuleInspectionItemDTO(
                    rule=item.rule,
                    condition=item.condition,
                    description=item.description,
                    matched=item.matched,
                    contribution=item.contribution,
                )
                for item in rule_inspection
            ],
            decision_flow=decision_flow,
            audit_logs=[
                AuditLogItemDTO(
                    id=item.id,
                    created_at=item.created_at,
                    actor=item.actor,
                    action=item.action,
                    details=item.details,
                )
                for item in audit_logs
            ],
        )

    async def get_timeline(self, join_request_id: uuid.UUID):
        detail = await self.get_investigation_detail(join_request_id)
        if detail is None:
            return None
        return detail.timeline

    async def export_case(
        self,
        join_request_id: uuid.UUID,
        *,
        export_format: str,
        write_audit: bool = True,
    ) -> tuple[bytes, str, str] | None:
        detail = await self.get_investigation_detail(join_request_id)
        if detail is None:
            return None

        payload = self.build_export_payload(detail)
        if export_format == "pdf":
            content = export_case_pdf(payload)
            media_type = "application/pdf"
            filename = f"investigation-{join_request_id}.pdf"
            action = "export_pdf"
        else:
            content = export_case_json(payload)
            media_type = "application/json"
            filename = f"investigation-{join_request_id}.json"
            action = "export_json"

        if write_audit:
            await self._write_audit(
                join_request_id,
                action=action,
                details={"format": export_format},
            )
        return content, media_type, filename

    async def replay_analysis(
        self,
        join_request_id: uuid.UUID,
        *,
        policy_version_id: uuid.UUID | None = None,
    ) -> ReplayResultDTO | None:
        row = await self._repo.get_investigation(join_request_id)
        if row is None:
            return None

        policy = await PolicyService(self._session).get_effective_policy(policy_version_id)
        rule_engine = policy.build_rule_engine()
        decision_engine = policy.build_decision_engine()
        risk_profile_builder = RiskProfileBuilder(thresholds=decision_engine.thresholds)

        features = self._feature_extractor.extract(row.telegram_user)
        rule_result = rule_engine.evaluate(features)
        trust_score = await self._reputation_service.get_score(row.telegram_user.id)
        history = await self._reputation_service.get_history(row.telegram_user.id, limit=5)
        history_lines = [
            f"{item.reason.value}: {item.old_score:.0f} -> {item.new_score:.0f}"
            for item in history
        ]
        risk_profile = risk_profile_builder.build(
            features,
            rule_result,
            trust_score=trust_score,
            rule_score=float(rule_result.rule_score),
            history=history_lines or None,
        )
        rule_engine_decision = decision_engine.decide(rule_result.rule_score)
        ai_service_result = self._ai_service.analyze(rule_engine_decision, risk_profile)
        final_decision = JoinRequestProcessingService._resolve_final_decision(
            rule_engine_decision,
            ai_service_result,
        )
        ai_score = JoinRequestProcessingService._resolve_ai_score(ai_service_result)
        prompt = self._prompt_builder.build(risk_profile)
        ai_response = (
            ai_service_result.analysis.to_dict()
            if ai_service_result.analysis is not None
            else None
        )

        await self._write_audit(
            join_request_id,
            action="replay",
            details={
                "rule_score": rule_result.rule_score,
                "rule_engine_decision": rule_engine_decision.value,
                "ai_status": ai_service_result.status.value,
                "final_decision": final_decision.value,
                "policy_version_number": policy.version_number,
                "policy_version_id": str(policy.version_id) if policy.version_id else None,
            },
        )

        return ReplayResultDTO(
            rule_score=rule_result.rule_score,
            rule_engine_decision=rule_engine_decision.value,
            ai_status=ai_service_result.status.value,
            ai_decision=ai_response.get("decision") if ai_response else None,
            ai_score=ai_score,
            final_decision=final_decision.value,
            prompt=PromptViewDTO(system_prompt=prompt.system, user_prompt=prompt.user),
            ai_response=ai_response,
            triggered_rules=[{"rule": item.rule, "score": item.score} for item in rule_result.triggered_rules],
            policy_version_number=policy.version_number,
            policy_version_id=policy.version_id,
        )

    async def list_channels_for_filter(self) -> list[tuple[uuid.UUID, str]]:
        return await self._repo.list_channels_for_filter()

    def build_export_payload(self, detail: InvestigationDetailDTO) -> dict[str, Any]:
        return sanitize_payload(
            {
                "id": str(detail.case.id),
                "channel_id": str(detail.channel_id),
                "channel_title": detail.case.channel_title,
                "status": detail.case.status.value,
                "user": {
                    "telegram_id": detail.case.user.telegram_id,
                    "username": detail.case.user.username,
                    "first_name": detail.case.user.first_name,
                    "last_name": detail.case.user.last_name,
                },
                "scores": {
                    "rule_score": detail.case.rule_score,
                    "ai_score": detail.case.ai_score,
                    "final_score": detail.case.final_score,
                    "trust_score": detail.case.trust_score,
                },
                "timeline": [
                    {
                        "stage": item.stage,
                        "title": item.title,
                        "timestamp": item.timestamp.isoformat() if item.timestamp else None,
                        "duration_ms": item.duration_ms,
                        "result": item.result,
                        "details": item.details,
                    }
                    for item in detail.timeline
                ],
                "prompt": {
                    "system": detail.prompt.system_prompt,
                    "user": detail.prompt.user_prompt,
                }
                if detail.prompt
                else None,
                "ai_response": {
                    "parsed": detail.ai_response.parsed_response,
                    "raw_json": detail.ai_response.raw_json,
                    "ai_status": detail.ai_response.ai_status,
                },
                "rule_inspection": [
                    {
                        "rule": item.rule,
                        "condition": item.condition,
                        "description": item.description,
                        "matched": item.matched,
                        "contribution": item.contribution,
                    }
                    for item in detail.rule_inspection
                ],
                "decision_flow": {
                    "rule_engine_decision": detail.decision_flow.rule_engine_decision,
                    "ai_decision": detail.decision_flow.ai_decision,
                    "final_decision": detail.decision_flow.final_decision,
                    "human_decision": detail.decision_flow.human_decision,
                    "ai_matches_human": detail.decision_flow.ai_matches_human,
                    "verdict": detail.decision_flow.verdict,
                },
                "audit_logs": [
                    {
                        "created_at": item.created_at.isoformat(),
                        "actor": item.actor,
                        "action": item.action,
                        "details": item.details,
                    }
                    for item in detail.audit_logs
                ],
            }
        )

    async def _write_audit(
        self,
        join_request_id: uuid.UUID,
        *,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        await self._audit_repo.create(
            AuditLog(
                actor=self.ACTOR,
                action=action,
                entity="join_request",
                entity_id=join_request_id,
                details=json.dumps(details, ensure_ascii=False, default=str) if details else None,
            )
        )

    def _build_prompt_view(self, row, explanation: dict[str, Any]) -> PromptViewDTO | None:
        if explanation.get("legacy_explanation") and not explanation.get("risk_profile"):
            return None
        if explanation.get("ai_status") == AIServiceStatus.SKIPPED.value:
            features = self._feature_extractor.extract(row.telegram_user)
            rule_result = self._rule_engine.evaluate(features)
            trust_score = explanation.get("risk_profile", {}).get("trust_score")
            if trust_score is None:
                return None
            risk_profile = self._risk_profile_builder.build(
                features,
                rule_result,
                trust_score=float(trust_score),
                rule_score=float(rule_result.rule_score),
            )
            prompt = self._prompt_builder.build(risk_profile)
            return PromptViewDTO(system_prompt=prompt.system, user_prompt=prompt.user)

        risk_data = explanation.get("risk_profile") or {}
        if not risk_data:
            return None
        features = self._feature_extractor.extract(row.telegram_user)
        rule_result = self._rule_engine.evaluate(features)
        risk_profile = self._risk_profile_builder.build(
            features,
            rule_result,
            trust_score=float(risk_data.get("trust_score") or 50),
            rule_score=float(row.analysis.rule_score if row.analysis else rule_result.rule_score),
            history=risk_data.get("history"),
        )
        prompt = self._prompt_builder.build(risk_profile)
        return PromptViewDTO(system_prompt=prompt.system, user_prompt=prompt.user)

    @staticmethod
    def _build_ai_response_view(
        explanation: dict[str, Any],
        raw_explanation: str | None,
    ) -> AIResponseViewDTO:
        parsed = explanation.get("ai_result")
        raw_json = None
        if parsed is not None:
            raw_json = json.dumps(parsed, ensure_ascii=False, indent=2, default=str)
        elif raw_explanation:
            raw_json = raw_explanation
        return AIResponseViewDTO(
            parsed_response=parsed,
            raw_json=raw_json,
            ai_status=explanation.get("ai_status"),
        )

    @staticmethod
    def _build_decision_flow(
        *,
        rule_engine_decision: AnalysisDecision | None,
        analysis,
        explanation: dict[str, Any],
        feedback,
        join_status: JoinRequestStatus,
    ) -> DecisionFlowDTO:
        ai_result = explanation.get("ai_result") or {}
        ai_decision = ai_result.get("decision")
        if ai_decision is None and analysis and analysis.decision:
            if explanation.get("ai_status") not in {None, AIServiceStatus.SKIPPED.value}:
                ai_decision = analysis.decision.value

        final_decision = analysis.decision.value if analysis and analysis.decision else None
        human_decision = feedback.human_decision.value if feedback else None
        if human_decision is None and join_status in {
            JoinRequestStatus.APPROVED,
            JoinRequestStatus.REJECTED,
        }:
            mapping = {
                JoinRequestStatus.APPROVED: AnalysisDecision.APPROVED.value,
                JoinRequestStatus.REJECTED: AnalysisDecision.REJECTED.value,
            }
            human_decision = mapping.get(join_status)

        ai_matches_human = None
        verdict = None
        verdict_class = None
        if ai_decision and human_decision:
            ai_matches_human = ai_decision == human_decision
            if ai_matches_human:
                verdict = "AI совпал с администратором"
                verdict_class = "success"
            else:
                verdict = "AI не совпал с администратором"
                verdict_class = "danger"

        return DecisionFlowDTO(
            rule_engine_decision=rule_engine_decision.value if rule_engine_decision else None,
            ai_decision=str(ai_decision) if ai_decision else None,
            final_decision=final_decision,
            human_decision=human_decision,
            ai_matches_human=ai_matches_human,
            verdict=verdict,
            verdict_class=verdict_class,
        )

    @staticmethod
    def _map_timeline_event(item):
        from app.schemas.investigation import TimelineEventDTO

        return TimelineEventDTO(
            stage=item.stage,
            title=item.title,
            timestamp=item.timestamp,
            duration_ms=item.duration_ms,
            result=item.result,
            details=item.details,
        )

    @staticmethod
    def build_filters(
        *,
        channel_id: uuid.UUID | None = None,
        status: str = "all",
        ai_decision: AnalysisDecision | None = None,
        human_decision: AnalysisDecision | None = None,
        trust_min: float | None = None,
        trust_max: float | None = None,
        rule_min: float | None = None,
        rule_max: float | None = None,
        ai_min: float | None = None,
        ai_max: float | None = None,
        date_from=None,
        date_to=None,
        search: str | None = None,
    ) -> InvestigationFilters:
        safe_status: InvestigationStatusFilter = status if status in STATUS_FILTER_MAP else "all"
        return InvestigationFilters(
            channel_id=channel_id,
            status=safe_status,
            ai_decision=ai_decision,
            human_decision=human_decision,
            trust_min=trust_min,
            trust_max=trust_max,
            rule_min=rule_min,
            rule_max=rule_max,
            ai_min=ai_min,
            ai_max=ai_max,
            date_from=date_from,
            date_to=date_to,
            search=search,
        )
