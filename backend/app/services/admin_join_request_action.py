import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai_analysis import AIAnalysis
from app.models.ai_feedback import AIFeedback
from app.models.audit_log import AuditLog
from app.models.blacklist import Blacklist
from app.models.enums import AnalysisDecision, JoinRequestStatus
from app.models.join_request import JoinRequest
from app.models.manual_review import AdminAction, ManualReview
from app.models.telegram_channel import TelegramChannel
from app.models.telegram_user import TelegramUser
from app.models.whitelist import Whitelist
from app.repositories.deps import (
    get_ai_analysis_repository,
    get_ai_feedback_repository,
    get_audit_log_repository,
    get_blacklist_repository,
    get_join_request_repository,
    get_manual_review_repository,
    get_whitelist_repository,
)
from app.reputation.enums import ReputationChangeReason
from app.reputation.service import ReputationService
from app.utils.logging import get_logger

logger = get_logger(__name__)

ACTIVE_STATUSES = {JoinRequestStatus.PENDING, JoinRequestStatus.MANUAL_REVIEW}
FINAL_STATUSES = {JoinRequestStatus.APPROVED, JoinRequestStatus.REJECTED}

BotFactory = Callable[[str], Awaitable[Bot]]


@dataclass(slots=True)
class AdminActionResult:
    success: bool
    message: str
    error: str | None = None


@dataclass(slots=True)
class JoinRequestActionContext:
    join_request: JoinRequest
    channel: TelegramChannel
    telegram_user: TelegramUser
    analysis: AIAnalysis | None


class AdminJoinRequestActionService:
    ACTOR = "admin_dashboard"

    def __init__(
        self,
        session: AsyncSession,
        *,
        bot_factory: BotFactory | None = None,
    ) -> None:
        self._session = session
        self._join_request_repo = get_join_request_repository(session)
        self._analysis_repo = get_ai_analysis_repository(session)
        self._whitelist_repo = get_whitelist_repository(session)
        self._blacklist_repo = get_blacklist_repository(session)
        self._audit_log_repo = get_audit_log_repository(session)
        self._manual_review_repo = get_manual_review_repository(session)
        self._ai_feedback_repo = get_ai_feedback_repository(session)
        self._bot_factory = bot_factory or self._default_bot_factory
        self._reputation_service = ReputationService(session)

    async def approve(self, join_request_id: uuid.UUID) -> AdminActionResult:
        return await self._execute_decision_action(
            join_request_id,
            admin_action=AdminAction.APPROVE,
            final_decision=AnalysisDecision.APPROVED,
            final_status=JoinRequestStatus.APPROVED,
            telegram_action="approve",
            success_message="Пользователь одобрен.",
        )

    async def reject(self, join_request_id: uuid.UUID) -> AdminActionResult:
        return await self._execute_decision_action(
            join_request_id,
            admin_action=AdminAction.REJECT,
            final_decision=AnalysisDecision.REJECTED,
            final_status=JoinRequestStatus.REJECTED,
            telegram_action="decline",
            success_message="Заявка отклонена.",
        )

    async def whitelist(self, join_request_id: uuid.UUID) -> AdminActionResult:
        context = await self._load_context(join_request_id)
        if context is None:
            return AdminActionResult(success=False, message="Заявка не найдена.", error="not_found")

        if not await self._whitelist_repo.exists_by_telegram_user_id(context.telegram_user.id):
            await self._whitelist_repo.create(
                Whitelist(telegram_user_id=context.telegram_user.id, approved_by=None)
            )
            await self._reputation_service.set_whitelist(context.telegram_user.id)

        previous_analysis_decision = (
            context.analysis.decision if context.analysis else AnalysisDecision.MANUAL_REVIEW
        )

        telegram_error: str | None = None
        if context.join_request.status in ACTIVE_STATUSES:
            telegram_error = await self._call_telegram(
                bot_token=context.channel.bot.bot_token,
                chat_id=context.channel.telegram_chat_id,
                user_id=context.telegram_user.telegram_id,
                action="approve",
            )
            if telegram_error is None:
                context.join_request.status = JoinRequestStatus.APPROVED
                await self._join_request_repo.update(context.join_request)
                await self._update_analysis_decision(context.analysis, AnalysisDecision.APPROVED)

        await self._record_feedback(
            context=context,
            admin_action=AdminAction.WHITELIST,
            human_decision=AnalysisDecision.APPROVED,
            previous_analysis_decision=previous_analysis_decision,
        )
        await self._write_audit(
            action="whitelist",
            entity_id=context.join_request.id,
            error=telegram_error,
        )

        if telegram_error:
            return AdminActionResult(
                success=False,
                message="Пользователь добавлен в whitelist, но Telegram вернул ошибку.",
                error=telegram_error,
            )
        return AdminActionResult(success=True, message="Пользователь добавлен в whitelist.")

    async def blacklist(self, join_request_id: uuid.UUID) -> AdminActionResult:
        context = await self._load_context(join_request_id)
        if context is None:
            return AdminActionResult(success=False, message="Заявка не найдена.", error="not_found")

        if not await self._blacklist_repo.exists_by_telegram_user_id(context.telegram_user.id):
            await self._blacklist_repo.create(
                Blacklist(
                    telegram_user_id=context.telegram_user.id,
                    reason="Manual admin blacklist",
                    confidence=1.0,
                    source="admin_dashboard",
                )
            )
            await self._reputation_service.set_blacklist(context.telegram_user.id)

        previous_analysis_decision = (
            context.analysis.decision if context.analysis else AnalysisDecision.MANUAL_REVIEW
        )

        telegram_error: str | None = None
        if context.join_request.status in ACTIVE_STATUSES:
            telegram_error = await self._call_telegram(
                bot_token=context.channel.bot.bot_token,
                chat_id=context.channel.telegram_chat_id,
                user_id=context.telegram_user.telegram_id,
                action="decline",
            )
            if telegram_error is None:
                context.join_request.status = JoinRequestStatus.REJECTED
                await self._join_request_repo.update(context.join_request)
                await self._update_analysis_decision(context.analysis, AnalysisDecision.REJECTED)

        await self._record_feedback(
            context=context,
            admin_action=AdminAction.BLACKLIST,
            human_decision=AnalysisDecision.REJECTED,
            previous_analysis_decision=previous_analysis_decision,
        )
        await self._write_audit(
            action="blacklist",
            entity_id=context.join_request.id,
            error=telegram_error,
        )

        if telegram_error:
            return AdminActionResult(
                success=False,
                message="Пользователь добавлен в blacklist, но Telegram вернул ошибку.",
                error=telegram_error,
            )
        return AdminActionResult(success=True, message="Пользователь добавлен в blacklist.")

    async def _execute_decision_action(
        self,
        join_request_id: uuid.UUID,
        *,
        admin_action: AdminAction,
        final_decision: AnalysisDecision,
        final_status: JoinRequestStatus,
        telegram_action: str,
        success_message: str,
    ) -> AdminActionResult:
        context = await self._load_context(join_request_id)
        if context is None:
            return AdminActionResult(success=False, message="Заявка не найдена.", error="not_found")

        if context.join_request.status in FINAL_STATUSES:
            return AdminActionResult(
                success=False,
                message="Заявка уже имеет финальный статус.",
                error="already_final",
            )

        previous_analysis_decision = (
            context.analysis.decision if context.analysis else AnalysisDecision.MANUAL_REVIEW
        )

        telegram_error = await self._call_telegram(
            bot_token=context.channel.bot.bot_token,
            chat_id=context.channel.telegram_chat_id,
            user_id=context.telegram_user.telegram_id,
            action=telegram_action,
        )

        if telegram_error is not None:
            await self._write_audit(
                action=admin_action.value.lower(),
                entity_id=context.join_request.id,
                error=telegram_error,
            )
            return AdminActionResult(
                success=False,
                message="Не удалось выполнить действие в Telegram.",
                error=telegram_error,
            )

        context.join_request.status = final_status
        await self._join_request_repo.update(context.join_request)
        await self._update_analysis_decision(context.analysis, final_decision)

        await self._record_feedback(
            context=context,
            admin_action=admin_action,
            human_decision=final_decision,
            previous_analysis_decision=previous_analysis_decision,
        )
        await self._write_audit(action=admin_action.value.lower(), entity_id=context.join_request.id)

        if admin_action == AdminAction.APPROVE:
            await self._reputation_service.increase(
                context.telegram_user.id,
                reason=ReputationChangeReason.MANUAL_APPROVED,
            )
        elif admin_action == AdminAction.REJECT:
            await self._reputation_service.decrease(
                context.telegram_user.id,
                reason=ReputationChangeReason.MANUAL_REJECTED,
            )

        return AdminActionResult(success=True, message=success_message)

    async def _load_context(self, join_request_id: uuid.UUID) -> JoinRequestActionContext | None:
        stmt = (
            select(JoinRequest)
            .options(
                selectinload(JoinRequest.channel).selectinload(TelegramChannel.bot),
                selectinload(JoinRequest.telegram_user),
                selectinload(JoinRequest.ai_analyses),
            )
            .where(JoinRequest.id == join_request_id)
        )
        join_request = (await self._session.execute(stmt)).scalar_one_or_none()
        if join_request is None:
            return None

        analysis = None
        if join_request.ai_analyses:
            analysis = max(join_request.ai_analyses, key=lambda item: item.created_at)

        return JoinRequestActionContext(
            join_request=join_request,
            channel=join_request.channel,
            telegram_user=join_request.telegram_user,
            analysis=analysis,
        )

    async def _call_telegram(
        self,
        *,
        bot_token: str,
        chat_id: int,
        user_id: int,
        action: str,
    ) -> str | None:
        bot = await self._bot_factory(bot_token)
        try:
            if action == "approve":
                await bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
            elif action == "decline":
                await bot.decline_chat_join_request(chat_id=chat_id, user_id=user_id)
            return None
        except Exception as exc:
            logger.error(
                "Admin Telegram action failed | chat_id=%s user_id=%s action=%s error=%s",
                chat_id,
                user_id,
                action,
                exc,
                exc_info=True,
            )
            return str(exc)
        finally:
            await bot.session.close()

    async def _update_analysis_decision(
        self,
        analysis: AIAnalysis | None,
        decision: AnalysisDecision,
    ) -> None:
        if analysis is None:
            return
        analysis.decision = decision
        await self._analysis_repo.update(analysis)

    async def _record_feedback(
        self,
        *,
        context: JoinRequestActionContext,
        admin_action: AdminAction,
        human_decision: AnalysisDecision,
        previous_analysis_decision: AnalysisDecision,
    ) -> None:
        await self._manual_review_repo.create(
            ManualReview(
                join_request_id=context.join_request.id,
                telegram_user_id=context.telegram_user.id,
                admin_action=admin_action,
                previous_decision=previous_analysis_decision,
                final_decision=human_decision,
                comment=None,
            )
        )

        if context.analysis is None:
            return

        await self._ai_feedback_repo.create(
            AIFeedback(
                join_request_id=context.join_request.id,
                rule_score=context.analysis.rule_score,
                ai_score=context.analysis.ai_score,
                ai_decision=previous_analysis_decision,
                human_decision=human_decision,
                was_ai_correct=previous_analysis_decision == human_decision,
            )
        )

    async def _write_audit(
        self,
        *,
        action: str,
        entity_id: uuid.UUID,
        error: str | None = None,
        details: str | None = None,
    ) -> None:
        audit_action = f"{action}_error" if error else action
        await self._audit_log_repo.create(
            AuditLog(
                actor=self.ACTOR,
                action=audit_action,
                entity="join_request",
                entity_id=entity_id,
                details=details,
            )
        )

    @staticmethod
    async def _default_bot_factory(bot_token: str) -> Bot:
        return Bot(token=bot_token)
