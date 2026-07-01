import json
import uuid
from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import ChatJoinRequest, User as TelegramProfile
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.cost import estimate_request_cost_usd
from app.ai.enums import AIServiceStatus
from app.ai.result import AIServiceResult
from app.ai.service import AIService
from app.models.ai_analysis import AIAnalysis
from app.models.ai_usage import AIUsage
from app.models.enums import AnalysisDecision, JoinRequestStatus
from app.models.join_request import JoinRequest
from app.models.telegram_user import TelegramUser
from app.repositories.deps import (
    get_ai_analysis_repository,
    get_ai_usage_repository,
    get_blacklist_repository,
    get_join_request_repository,
    get_telegram_channel_repository,
    get_telegram_user_repository,
    get_whitelist_repository,
)
from app.features import FeatureExtractor
from app.reputation import ReputationEngine
from app.reputation.service import ReputationService
from app.risk import RiskProfile, RiskProfileBuilder
from app.risk.enums import RiskLevel
from app.rules.engine import RuleEngine, RuleEngineResult
from app.services.decision_engine import DecisionEngine
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class JoinRequestProcessingResult:
    join_request: JoinRequest
    telegram_user: TelegramUser
    rule_result: RuleEngineResult
    risk_profile: RiskProfile
    decision: AnalysisDecision
    analysis: AIAnalysis
    channel_title: str
    action_taken: str


class JoinRequestProcessingService:
    def __init__(
        self,
        session: AsyncSession,
        bot: Bot,
        rule_engine: RuleEngine | None = None,
        decision_engine: DecisionEngine | None = None,
        risk_profile_builder: RiskProfileBuilder | None = None,
        ai_service: AIService | None = None,
    ) -> None:
        self._session = session
        self._bot = bot
        self._rule_engine_override = rule_engine
        self._decision_engine_override = decision_engine
        self._use_policy_engines = rule_engine is None and decision_engine is None
        self._rule_engine = rule_engine or RuleEngine()
        self._decision_engine = decision_engine or DecisionEngine()
        self._risk_profile_builder = risk_profile_builder or RiskProfileBuilder(
            thresholds=self._decision_engine.thresholds,
        )
        self._ai_service = ai_service or AIService()
        self._feature_extractor = FeatureExtractor()
        self._telegram_user_repo = get_telegram_user_repository(session)
        self._channel_repo = get_telegram_channel_repository(session)
        self._join_request_repo = get_join_request_repository(session)
        self._analysis_repo = get_ai_analysis_repository(session)
        self._ai_usage_repo = get_ai_usage_repository(session)
        self._whitelist_repo = get_whitelist_repository(session)
        self._blacklist_repo = get_blacklist_repository(session)
        self._reputation_service = ReputationService(session)

    async def process(self, event: ChatJoinRequest) -> JoinRequestProcessingResult | None:
        if event.from_user is None:
            logger.warning("Join request ignored: missing from_user")
            return None

        channel = await self._channel_repo.get_by_telegram_chat_id(event.chat.id)
        if channel is None:
            logger.warning(
                "Join request ignored: channel not registered | channel_id=%s",
                event.chat.id,
            )
            return None

        if not channel.is_active:
            logger.info(
                "Join request ignored: channel disabled | channel_id=%s | chat_id=%s",
                channel.id,
                event.chat.id,
            )
            return None

        telegram_user = await self._upsert_telegram_user(event.from_user)
        join_request = await self._join_request_repo.create(
            JoinRequest(
                channel_id=channel.id,
                telegram_user_id=telegram_user.id,
                status=JoinRequestStatus.PENDING,
            )
        )

        if await self._whitelist_repo.exists_by_telegram_user_id(telegram_user.id):
            return await self._process_list_match(
                event=event,
                channel=channel,
                telegram_user=telegram_user,
                join_request=join_request,
                decision=AnalysisDecision.APPROVED,
                explanation="whitelist_match",
            )

        if await self._blacklist_repo.exists_by_telegram_user_id(telegram_user.id):
            return await self._process_list_match(
                event=event,
                channel=channel,
                telegram_user=telegram_user,
                join_request=join_request,
                decision=AnalysisDecision.REJECTED,
                explanation="blacklist_match",
            )

        trust_score = await self._reputation_service.get_score(telegram_user.id)
        if ReputationEngine.should_auto_approve(trust_score):
            return await self._process_list_match(
                event=event,
                channel=channel,
                telegram_user=telegram_user,
                join_request=join_request,
                decision=AnalysisDecision.APPROVED,
                explanation="reputation_auto_approve",
                trust_score=trust_score,
            )

        if ReputationEngine.should_auto_reject(trust_score):
            return await self._process_list_match(
                event=event,
                channel=channel,
                telegram_user=telegram_user,
                join_request=join_request,
                decision=AnalysisDecision.REJECTED,
                explanation="reputation_auto_reject",
                trust_score=trust_score,
            )

        features = self._feature_extractor.extract(telegram_user)
        rule_engine, decision_engine, risk_profile_builder = await self._resolve_engines(channel.organization_id)
        rule_result = rule_engine.evaluate(features)
        reputation_history = await self._reputation_service.get_history(telegram_user.id, limit=5)
        history_lines = [
            f"{item.reason.value}: {item.old_score:.0f} -> {item.new_score:.0f}"
            for item in reputation_history
        ]
        risk_profile = risk_profile_builder.build(
            features,
            rule_result,
            trust_score=trust_score,
            rule_score=float(rule_result.rule_score),
            history=history_lines or None,
        )
        initial_decision = decision_engine.decide(rule_result.rule_score)

        ai_service_result: AIServiceResult | None = None
        if initial_decision == AnalysisDecision.MANUAL_REVIEW:
            ai_service = await self._resolve_ai_service(channel.organization_id)
            ai_service_result = ai_service.analyze(initial_decision, risk_profile)
            await self._persist_ai_usage(ai_service_result, channel.organization_id)

        final_decision = self._resolve_final_decision(initial_decision, ai_service_result)
        ai_score = self._resolve_ai_score(ai_service_result)
        final_score = self._calculate_final_score(rule_result.rule_score, ai_score)
        explanation = self._build_explanation(rule_result, risk_profile, ai_service_result)

        analysis = await self._analysis_repo.create(
            AIAnalysis(
                join_request_id=join_request.id,
                rule_score=float(rule_result.rule_score),
                ai_score=float(ai_score) if ai_score is not None else None,
                final_score=final_score,
                decision=final_decision,
                explanation=explanation,
            )
        )

        join_request.status = decision_engine.map_to_join_request_status(final_decision)
        await self._join_request_repo.update(join_request)

        action_taken = await self._apply_telegram_action(
            chat_id=event.chat.id,
            user_id=event.from_user.id,
            decision=final_decision,
            organization_id=channel.organization_id,
        )

        channel_title = channel.title
        self._log_processing(
            telegram_id=event.from_user.id,
            username=event.from_user.username,
            rule_score=rule_result.rule_score,
            ai_score=ai_score,
            final_score=final_score,
            decision=final_decision.value,
            ai_status=self._resolve_ai_status(ai_service_result),
            channel=channel_title,
            action=action_taken,
        )

        return JoinRequestProcessingResult(
            join_request=join_request,
            telegram_user=telegram_user,
            rule_result=rule_result,
            risk_profile=risk_profile,
            decision=final_decision,
            analysis=analysis,
            channel_title=channel_title,
            action_taken=action_taken,
        )

    async def _resolve_engines(self, organization_id: uuid.UUID | None):
        if not self._use_policy_engines:
            return self._rule_engine, self._decision_engine, self._risk_profile_builder
        from app.services.policy import PolicyService

        policy = await PolicyService(
            self._session,
            organization_id=organization_id,
        ).get_effective_policy()
        rule_engine = policy.build_rule_engine()
        decision_engine = policy.build_decision_engine()
        risk_profile_builder = RiskProfileBuilder(thresholds=decision_engine.thresholds)
        return rule_engine, decision_engine, risk_profile_builder

    async def _resolve_ai_service(self, organization_id: uuid.UUID | None) -> AIService:
        from app.ai.openrouter_provider import OpenRouterProvider
        from app.config.runtime_overrides import get_runtime_snapshot
        from app.services.organization import OrganizationSecretsRuntime

        org_key = await OrganizationSecretsRuntime(self._session).resolve_openrouter_api_key(
            organization_id
        )
        if org_key:
            snapshot = get_runtime_snapshot()
            provider = OpenRouterProvider(api_key=org_key, model=snapshot.openrouter_model)
            return AIService(provider=provider)
        return self._ai_service

    async def _process_list_match(
        self,
        *,
        event: ChatJoinRequest,
        channel,
        telegram_user: TelegramUser,
        join_request: JoinRequest,
        decision: AnalysisDecision,
        explanation: str,
        trust_score: float | None = None,
    ) -> JoinRequestProcessingResult:
        assert event.from_user is not None

        if trust_score is None:
            trust_score = await self._reputation_service.get_score(telegram_user.id)
        analysis = await self._analysis_repo.create(
            AIAnalysis(
                join_request_id=join_request.id,
                rule_score=0.0,
                ai_score=None,
                final_score=0.0,
                decision=decision,
                explanation=explanation,
            )
        )

        join_request.status = self._decision_engine.map_to_join_request_status(decision)
        await self._join_request_repo.update(join_request)

        action_taken = await self._apply_telegram_action(
            chat_id=event.chat.id,
            user_id=event.from_user.id,
            decision=decision,
            organization_id=channel.organization_id,
        )

        empty_rule_result = RuleEngineResult(rule_score=0, triggered_rules=[])
        empty_risk = RiskProfile(
            risk_level=RiskLevel.LOW,
            confidence=1.0,
            signals=[],
            summary=explanation,
            main_reason=explanation,
            trust_score=trust_score,
        )

        self._log_processing(
            telegram_id=event.from_user.id,
            username=event.from_user.username,
            rule_score=0,
            ai_score=None,
            final_score=0.0,
            decision=decision.value,
            ai_status=AIServiceStatus.SKIPPED.value,
            channel=channel.title,
            action=action_taken,
        )

        return JoinRequestProcessingResult(
            join_request=join_request,
            telegram_user=telegram_user,
            rule_result=empty_rule_result,
            risk_profile=empty_risk,
            decision=decision,
            analysis=analysis,
            channel_title=channel.title,
            action_taken=action_taken,
        )

    async def _upsert_telegram_user(self, profile: TelegramProfile) -> TelegramUser:
        has_photo = await self._resolve_has_photo(profile.id)
        existing = await self._telegram_user_repo.get_by_telegram_id(profile.id)

        if existing is None:
            return await self._telegram_user_repo.create(
                TelegramUser(
                    telegram_id=profile.id,
                    username=profile.username,
                    first_name=profile.first_name,
                    last_name=profile.last_name,
                    language_code=profile.language_code,
                    is_premium=profile.is_premium or False,
                    has_photo=has_photo,
                )
            )

        existing.username = profile.username
        existing.first_name = profile.first_name
        existing.last_name = profile.last_name
        existing.language_code = profile.language_code
        existing.is_premium = profile.is_premium or False
        existing.has_photo = has_photo
        return await self._telegram_user_repo.update(existing)

    async def _resolve_has_photo(self, user_id: int) -> bool:
        try:
            photos = await self._bot.get_user_profile_photos(user_id, limit=1)
            return photos.total_count > 0
        except Exception as exc:
            logger.warning(
                "Failed to resolve profile photo | user_id=%s error=%s",
                user_id,
                exc,
            )
            return False

    async def _apply_telegram_action(
        self,
        *,
        chat_id: int,
        user_id: int,
        decision: AnalysisDecision,
        organization_id: uuid.UUID | None = None,
    ) -> str:
        from app.services.telegram_runtime import TelegramRuntimeService

        bot = await TelegramRuntimeService(self._session).get_bot(
            organization_id,
            fallback=self._bot,
        )
        close_bot = bot is not self._bot
        try:
            if decision == AnalysisDecision.APPROVED:
                await bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
                return "approved"
            if decision == AnalysisDecision.REJECTED:
                await bot.decline_chat_join_request(chat_id=chat_id, user_id=user_id)
                return "declined"
            return "left_pending"
        except Exception as exc:
            logger.error(
                "Telegram action failed | chat_id=%s user_id=%s decision=%s error=%s",
                chat_id,
                user_id,
                decision.value,
                exc,
                exc_info=True,
            )
            return "telegram_action_failed"
        finally:
            if close_bot:
                await bot.session.close()

    @staticmethod
    def _resolve_final_decision(
        initial_decision: AnalysisDecision,
        ai_service_result: AIServiceResult | None,
    ) -> AnalysisDecision:
        if initial_decision != AnalysisDecision.MANUAL_REVIEW:
            return initial_decision
        if ai_service_result is None:
            return initial_decision
        if ai_service_result.status in (
            AIServiceStatus.SUCCESS,
            AIServiceStatus.FALLBACK,
        ):
            assert ai_service_result.analysis is not None
            return ai_service_result.analysis.decision
        return AnalysisDecision.MANUAL_REVIEW

    @staticmethod
    def _resolve_ai_score(ai_service_result: AIServiceResult | None) -> int | None:
        if ai_service_result is None:
            return None
        if ai_service_result.status not in (
            AIServiceStatus.SUCCESS,
            AIServiceStatus.FALLBACK,
        ):
            return None
        assert ai_service_result.analysis is not None
        return ai_service_result.analysis.ai_score

    @staticmethod
    def _resolve_ai_status(ai_service_result: AIServiceResult | None) -> str:
        if ai_service_result is None:
            return AIServiceStatus.SKIPPED.value
        return ai_service_result.status.value

    @staticmethod
    def _calculate_final_score(rule_score: int, ai_score: int | None) -> float:
        if ai_score is None:
            return float(rule_score)
        return round((rule_score + ai_score) / 2, 2)

    @staticmethod
    def _build_explanation(
        rule_result: RuleEngineResult,
        risk_profile: RiskProfile,
        ai_service_result: AIServiceResult | None,
    ) -> str:
        payload = {
            "triggered_rules": [
                {"rule": item.rule, "score": item.score}
                for item in rule_result.triggered_rules
            ],
            "risk_profile": risk_profile.to_dict(),
            "ai_result": (
                ai_service_result.analysis.to_dict()
                if ai_service_result and ai_service_result.analysis
                else None
            ),
            "ai_status": (
                ai_service_result.status.value
                if ai_service_result
                else AIServiceStatus.SKIPPED.value
            ),
        }
        return json.dumps(payload, ensure_ascii=False)

    async def _persist_ai_usage(
        self,
        ai_service_result: AIServiceResult | None,
        organization_id: uuid.UUID | None = None,
    ) -> None:
        if ai_service_result is None or ai_service_result.analysis is None:
            return
        if ai_service_result.status not in {AIServiceStatus.SUCCESS, AIServiceStatus.FALLBACK}:
            return

        analysis = ai_service_result.analysis
        estimated_cost = estimate_request_cost_usd(
            analysis.model,
            analysis.prompt_tokens,
            analysis.completion_tokens,
        )
        await self._ai_usage_repo.create(
            AIUsage(
                organization_id=organization_id,
                provider=analysis.provider,
                model=analysis.model,
                prompt_tokens=analysis.prompt_tokens,
                completion_tokens=analysis.completion_tokens,
                total_tokens=analysis.total_tokens,
                estimated_cost=estimated_cost,
                latency_ms=analysis.response_time_ms,
            )
        )

    @staticmethod
    def _log_processing(
        *,
        telegram_id: int,
        username: str | None,
        rule_score: int,
        ai_score: int | None,
        final_score: float,
        decision: str,
        ai_status: str,
        channel: str,
        action: str,
    ) -> None:
        logger.info(
            (
                "Join request processed | Telegram ID: %s | Username: %s | "
                "Rule Score: %s | AI Score: %s | Final Score: %s | "
                "Decision: %s | AI Status: %s | Channel: %s | Action: %s"
            ),
            telegram_id,
            username or "—",
            rule_score,
            ai_score if ai_score is not None else "—",
            final_score,
            decision,
            ai_status,
            channel,
            action,
        )

