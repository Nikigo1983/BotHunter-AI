import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, ChatJoinRequest, User as TelegramProfile
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.enums import AIServiceStatus
from app.ai.mock_provider import MockAIProvider
from app.ai.service import AIService
from app.config.decision_settings import DecisionThresholds
from app.features import FeatureExtractor
from app.models.enums import AnalysisDecision, JoinRequestStatus
from app.models.reputation import Reputation
from app.models.telegram_bot import TelegramBot
from app.models.telegram_channel import TelegramChannel
from app.models.telegram_user import TelegramUser
from app.repositories.deps import (
    get_ai_analysis_repository,
    get_join_request_repository,
    get_reputation_repository,
    get_telegram_bot_repository,
    get_telegram_channel_repository,
    get_telegram_user_repository,
    get_user_repository,
)
from app.features.feature_set import FeatureSet
from app.risk import RiskLevel, RiskProfileBuilder
from app.rules.engine import RuleEngine, RuleEngineResult
from app.services.decision_engine import DecisionEngine
from app.services.join_request_processing import JoinRequestProcessingService
from tests.conftest import make_user

THRESHOLDS = DecisionThresholds(approve_below=30, reject_from=70)


def make_ai_service() -> AIService:
    mock_provider = MockAIProvider()
    return AIService(provider=mock_provider, fallback_provider=mock_provider, timeout=5.0)


async def create_registered_channel(session: AsyncSession, chat_id: int) -> TelegramChannel:
    user_repo = get_user_repository(session)
    bot_repo = get_telegram_bot_repository(session)
    channel_repo = get_telegram_channel_repository(session)

    owner = await user_repo.create(make_user(f"owner-{chat_id}"))
    bot = await bot_repo.create(
        TelegramBot(
            owner_id=owner.id,
            bot_token="token",
            bot_username=f"bot_{uuid.uuid4().hex[:8]}",
        )
    )
    return await channel_repo.create(
        TelegramChannel(
            owner_id=owner.id,
            bot_id=bot.id,
            telegram_chat_id=chat_id,
            title="Integration Channel",
            is_active=True,
        )
    )


def make_join_request_event(
    *,
    chat_id: int,
    user_id: int = 900001,
    username: str | None = "join_user",
    first_name: str = "Join",
    last_name: str | None = "User",
    language_code: str | None = "ru",
    is_premium: bool = False,
) -> ChatJoinRequest:
    return ChatJoinRequest(
        chat=Chat(id=chat_id, type=ChatType.CHANNEL, title="Integration Channel"),
        from_user=TelegramProfile(
            id=user_id,
            is_bot=False,
            first_name=first_name,
            last_name=last_name,
            username=username,
            language_code=language_code,
            is_premium=is_premium,
        ),
        user_chat_id=user_id,
        date=int(datetime.now(timezone.utc).timestamp()),
        bio=None,
    )


def make_service(
    session: AsyncSession,
    mock_bot: AsyncMock,
    *,
    rule_engine: RuleEngine | None = None,
) -> JoinRequestProcessingService:
    decision_engine = DecisionEngine(THRESHOLDS)
    return JoinRequestProcessingService(
        session,
        mock_bot,
        rule_engine=rule_engine or RuleEngine(),
        decision_engine=decision_engine,
        risk_profile_builder=RiskProfileBuilder(thresholds=THRESHOLDS),
        ai_service=make_ai_service(),
    )


@pytest.mark.asyncio
async def test_process_join_request_approved(session: AsyncSession) -> None:
    chat_id = -100700001
    await create_registered_channel(session, chat_id)

    mock_bot = AsyncMock()
    mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=1)

    class AlwaysApproveRuleEngine(RuleEngine):
        def evaluate(self, features: FeatureSet) -> RuleEngineResult:
            return RuleEngineResult(rule_score=10, triggered_rules=[])

    service = make_service(session, mock_bot, rule_engine=AlwaysApproveRuleEngine())
    result = await service.process(make_join_request_event(chat_id=chat_id))

    assert result is not None
    assert result.decision == AnalysisDecision.APPROVED
    assert result.join_request.status == JoinRequestStatus.APPROVED
    assert result.analysis.ai_score is None
    assert result.analysis.final_score == 10.0
    assert result.analysis.rule_score == 10.0

    explanation = json.loads(result.analysis.explanation or "{}")
    assert explanation["ai_status"] == AIServiceStatus.SKIPPED.value
    assert explanation["ai_result"] is None
    assert "risk_profile" in explanation

    mock_bot.approve_chat_join_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_join_request_manual_review_with_ai(session: AsyncSession) -> None:
    chat_id = -100700002
    await create_registered_channel(session, chat_id)

    mock_bot = AsyncMock()
    mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=0)

    class ManualReviewRuleEngine(RuleEngine):
        def evaluate(self, features: FeatureSet) -> RuleEngineResult:
            return RuleEngineResult(rule_score=45, triggered_rules=[])

    service = make_service(session, mock_bot, rule_engine=ManualReviewRuleEngine())
    result = await service.process(make_join_request_event(chat_id=chat_id, user_id=900002))

    assert result is not None
    assert result.risk_profile.risk_level == RiskLevel.MEDIUM
    assert result.analysis.ai_score is not None
    assert result.analysis.final_score == round((45 + result.analysis.ai_score) / 2, 2)
    assert result.decision == AnalysisDecision.MANUAL_REVIEW
    assert result.join_request.status == JoinRequestStatus.MANUAL_REVIEW
    assert result.action_taken == "left_pending"

    explanation = json.loads(result.analysis.explanation or "{}")
    assert explanation["ai_status"] in {
        AIServiceStatus.SUCCESS.value,
        AIServiceStatus.FALLBACK.value,
    }
    assert explanation["ai_result"] is not None

    mock_bot.approve_chat_join_request.assert_not_called()
    mock_bot.decline_chat_join_request.assert_not_called()


@pytest.mark.asyncio
async def test_process_join_request_rejected(session: AsyncSession) -> None:
    chat_id = -100700003
    await create_registered_channel(session, chat_id)

    mock_bot = AsyncMock()
    mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=0)

    class RejectRuleEngine(RuleEngine):
        def evaluate(self, features: FeatureSet) -> RuleEngineResult:
            return RuleEngineResult(rule_score=80, triggered_rules=[])

    service = make_service(session, mock_bot, rule_engine=RejectRuleEngine())
    result = await service.process(make_join_request_event(chat_id=chat_id, user_id=900003))

    assert result is not None
    assert result.decision == AnalysisDecision.REJECTED
    assert result.join_request.status == JoinRequestStatus.REJECTED
    assert result.analysis.ai_score is None
    mock_bot.decline_chat_join_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_join_request_persists_records(session: AsyncSession) -> None:
    chat_id = -100700004
    await create_registered_channel(session, chat_id)

    mock_bot = AsyncMock()
    mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=0)

    service = make_service(session, mock_bot)
    event = make_join_request_event(
        chat_id=chat_id,
        user_id=900004,
        username="risky_user",
        first_name="",
        last_name=None,
    )
    result = await service.process(event)

    assert result is not None
    telegram_user_repo = get_telegram_user_repository(session)
    join_request_repo = get_join_request_repository(session)
    analysis_repo = get_ai_analysis_repository(session)

    stored_user = await telegram_user_repo.get_by_telegram_id(900004)
    assert stored_user is not None
    assert stored_user.username == "risky_user"

    stored_join_request = await join_request_repo.get_by_id(result.join_request.id)
    assert stored_join_request is not None

    stored_analysis = await analysis_repo.get_by_id(result.analysis.id)
    assert stored_analysis is not None
    explanation = json.loads(stored_analysis.explanation or "{}")
    assert isinstance(explanation["triggered_rules"], list)
    assert "risk_profile" in explanation


@pytest.mark.asyncio
async def test_process_join_request_updates_existing_telegram_user(session: AsyncSession) -> None:
    chat_id = -100700005
    await create_registered_channel(session, chat_id)
    telegram_user_repo = get_telegram_user_repository(session)

    await telegram_user_repo.create(
        TelegramUser(
            telegram_id=900005,
            username="old_name",
            first_name="Old",
            last_name="Name",
            language_code="en",
            is_premium=False,
            has_photo=True,
        )
    )

    mock_bot = AsyncMock()
    mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=0)

    service = make_service(session, mock_bot)
    await service.process(
        make_join_request_event(
            chat_id=chat_id,
            user_id=900005,
            username="new_name",
            first_name="New",
            last_name="Name",
        )
    )

    updated = await telegram_user_repo.get_by_telegram_id(900005)
    assert updated is not None
    assert updated.username == "new_name"
    assert updated.first_name == "New"


@pytest.mark.asyncio
async def test_process_join_request_telegram_failure_keeps_db_records(
    session: AsyncSession,
) -> None:
    chat_id = -100700006
    await create_registered_channel(session, chat_id)

    mock_bot = AsyncMock()
    mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=1)
    mock_bot.approve_chat_join_request.side_effect = RuntimeError("telegram unavailable")

    class AlwaysApproveRuleEngine(RuleEngine):
        def evaluate(self, features: FeatureSet) -> RuleEngineResult:
            return RuleEngineResult(rule_score=10, triggered_rules=[])

    service = make_service(session, mock_bot, rule_engine=AlwaysApproveRuleEngine())
    result = await service.process(make_join_request_event(chat_id=chat_id, user_id=900006))

    assert result is not None
    assert result.action_taken == "telegram_action_failed"
    assert result.decision == AnalysisDecision.APPROVED
    assert result.join_request.status == JoinRequestStatus.APPROVED
    assert result.analysis.id is not None


async def seed_user_with_trust(
    session: AsyncSession,
    *,
    telegram_id: int,
    trust_score: float,
) -> None:
    telegram_user_repo = get_telegram_user_repository(session)
    reputation_repo = get_reputation_repository(session)
    user = await telegram_user_repo.create(
        TelegramUser(
            telegram_id=telegram_id,
            username=f"trust_{telegram_id}",
            first_name="Trust",
            last_name="User",
            language_code="ru",
            is_premium=False,
            has_photo=False,
        )
    )
    await reputation_repo.create(
        Reputation(
            telegram_user_id=user.id,
            reputation_score=trust_score,
        )
    )


@pytest.mark.asyncio
async def test_process_join_request_auto_approve_by_reputation(session: AsyncSession) -> None:
    chat_id = -100700010
    user_id = 900010
    await create_registered_channel(session, chat_id)
    await seed_user_with_trust(session, telegram_id=user_id, trust_score=95.0)

    mock_bot = AsyncMock()
    mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=0)

    class ShouldRejectRuleEngine(RuleEngine):
        def evaluate(self, features: FeatureSet) -> RuleEngineResult:
            return RuleEngineResult(rule_score=99, triggered_rules=[])

    service = make_service(session, mock_bot, rule_engine=ShouldRejectRuleEngine())
    result = await service.process(make_join_request_event(chat_id=chat_id, user_id=user_id))

    assert result is not None
    assert result.decision == AnalysisDecision.APPROVED
    assert result.analysis.explanation == "reputation_auto_approve"
    assert result.analysis.ai_score is None
    mock_bot.approve_chat_join_request.assert_awaited_once()
    mock_bot.decline_chat_join_request.assert_not_called()


@pytest.mark.asyncio
async def test_process_join_request_auto_reject_by_reputation(session: AsyncSession) -> None:
    chat_id = -100700011
    user_id = 900011
    await create_registered_channel(session, chat_id)
    await seed_user_with_trust(session, telegram_id=user_id, trust_score=5.0)

    mock_bot = AsyncMock()
    mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=1)

    class ShouldApproveRuleEngine(RuleEngine):
        def evaluate(self, features: FeatureSet) -> RuleEngineResult:
            return RuleEngineResult(rule_score=5, triggered_rules=[])

    service = make_service(session, mock_bot, rule_engine=ShouldApproveRuleEngine())
    result = await service.process(make_join_request_event(chat_id=chat_id, user_id=user_id))

    assert result is not None
    assert result.decision == AnalysisDecision.REJECTED
    assert result.analysis.explanation == "reputation_auto_reject"
    assert result.analysis.ai_score is None
    mock_bot.decline_chat_join_request.assert_awaited_once()
    mock_bot.approve_chat_join_request.assert_not_called()

