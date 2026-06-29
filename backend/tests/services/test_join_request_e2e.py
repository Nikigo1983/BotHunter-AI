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
from app.models.enums import AnalysisDecision, JoinRequestStatus
from app.models.telegram_bot import TelegramBot
from app.models.telegram_channel import TelegramChannel
from app.repositories.deps import get_telegram_bot_repository, get_telegram_channel_repository, get_user_repository
from app.risk import RiskLevel
from app.rules.engine import RuleEngine
from app.services.decision_engine import DecisionEngine
from app.services.join_request_processing import JoinRequestProcessingService
from app.risk import RiskProfileBuilder
from tests.conftest import make_user

THRESHOLDS = DecisionThresholds(approve_below=30, reject_from=70)


async def create_registered_channel(session: AsyncSession, chat_id: int) -> TelegramChannel:
    user_repo = get_user_repository(session)
    bot_repo = get_telegram_bot_repository(session)
    channel_repo = get_telegram_channel_repository(session)

    owner = await user_repo.create(make_user(f"e2e-{chat_id}"))
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
            title="E2E Channel",
            is_active=True,
        )
    )


def make_event(
    *,
    chat_id: int,
    user_id: int,
    username: str | None,
    first_name: str,
    last_name: str | None = None,
    language_code: str | None = "ru",
) -> ChatJoinRequest:
    return ChatJoinRequest(
        chat=Chat(id=chat_id, type=ChatType.CHANNEL, title="E2E Channel"),
        from_user=TelegramProfile(
            id=user_id,
            is_bot=False,
            first_name=first_name,
            last_name=last_name,
            username=username,
            language_code=language_code,
        ),
        user_chat_id=user_id,
        date=int(datetime.now(timezone.utc).timestamp()),
        bio=None,
    )


def make_pipeline_service(session: AsyncSession, mock_bot: AsyncMock) -> JoinRequestProcessingService:
    mock_provider = MockAIProvider()
    return JoinRequestProcessingService(
        session,
        mock_bot,
        rule_engine=RuleEngine(),
        decision_engine=DecisionEngine(THRESHOLDS),
        risk_profile_builder=RiskProfileBuilder(thresholds=THRESHOLDS),
        ai_service=AIService(provider=mock_provider, fallback_provider=mock_provider, timeout=5.0),
    )


@pytest.mark.asyncio
async def test_e2e_low_risk_approved_without_ai(session: AsyncSession) -> None:
    chat_id = -100800001
    await create_registered_channel(session, chat_id)

    mock_bot = AsyncMock()
    mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=1)

    service = make_pipeline_service(session, mock_bot)
    result = await service.process(
        make_event(
            chat_id=chat_id,
            user_id=910001,
            username="normal_user",
            first_name="Ivan",
            last_name="Petrov",
        )
    )

    assert result is not None
    assert result.risk_profile.risk_level == RiskLevel.LOW
    assert result.decision == AnalysisDecision.APPROVED
    assert result.analysis.ai_score is None
    assert result.analysis.final_score == float(result.rule_result.rule_score)
    assert result.action_taken == "approved"

    explanation = json.loads(result.analysis.explanation or "{}")
    assert explanation["ai_status"] == AIServiceStatus.SKIPPED.value
    mock_bot.approve_chat_join_request.assert_awaited_once()
    mock_bot.decline_chat_join_request.assert_not_called()


@pytest.mark.asyncio
async def test_e2e_high_risk_rejected_without_ai(session: AsyncSession) -> None:
    chat_id = -100800002
    await create_registered_channel(session, chat_id)

    mock_bot = AsyncMock()
    mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=0)

    service = make_pipeline_service(session, mock_bot)
    result = await service.process(
        make_event(
            chat_id=chat_id,
            user_id=910002,
            username="crypto1234567",
            first_name="Crypto",
            last_name="Bonus",
            language_code=None,
        )
    )

    assert result is not None
    assert result.risk_profile.risk_level == RiskLevel.HIGH
    assert result.decision == AnalysisDecision.REJECTED
    assert result.join_request.status == JoinRequestStatus.REJECTED
    assert result.analysis.ai_score is None
    assert result.action_taken == "declined"

    explanation = json.loads(result.analysis.explanation or "{}")
    assert explanation["ai_status"] == AIServiceStatus.SKIPPED.value
    mock_bot.decline_chat_join_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_e2e_medium_risk_uses_ai_decision(session: AsyncSession) -> None:
    chat_id = -100800003
    await create_registered_channel(session, chat_id)

    mock_bot = AsyncMock()
    mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=0)

    service = make_pipeline_service(session, mock_bot)
    result = await service.process(
        make_event(
            chat_id=chat_id,
            user_id=910003,
            username="user1234567",
            first_name="Join",
            last_name="User",
            language_code=None,
        )
    )

    assert result is not None
    assert result.risk_profile.risk_level == RiskLevel.MEDIUM
    assert result.rule_result.rule_score >= THRESHOLDS.approve_below
    assert result.rule_result.rule_score < THRESHOLDS.reject_from
    assert result.analysis.ai_score is not None
    assert result.analysis.final_score == round(
        (result.rule_result.rule_score + result.analysis.ai_score) / 2,
        2,
    )
    assert result.decision == AnalysisDecision.MANUAL_REVIEW
    assert result.join_request.status == JoinRequestStatus.MANUAL_REVIEW
    assert result.action_taken == "left_pending"

    explanation = json.loads(result.analysis.explanation or "{}")
    assert explanation["ai_status"] in {
        AIServiceStatus.SUCCESS.value,
        AIServiceStatus.FALLBACK.value,
    }
    assert explanation["ai_result"]["decision"] == AnalysisDecision.MANUAL_REVIEW.value
    mock_bot.approve_chat_join_request.assert_not_called()
    mock_bot.decline_chat_join_request.assert_not_called()
