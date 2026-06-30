import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reputation import Reputation
from app.models.reputation_history import ReputationHistory
from app.models.telegram_user import TelegramUser
from app.repositories.deps import get_reputation_history_repository, get_reputation_repository
from app.reputation.engine import DEFAULT_TRUST_SCORE, ReputationEngine
from app.reputation.enums import ReputationChangeReason, ReputationTrend
from app.reputation.service import ReputationService


async def create_telegram_user(session: AsyncSession, *, suffix: str) -> TelegramUser:
    from app.repositories.deps import get_telegram_user_repository

    return await get_telegram_user_repository(session).create(
        TelegramUser(
            telegram_id=int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000,
            username=f"rep_user_{suffix}",
            first_name="Rep",
            last_name="User",
            language_code="ru",
            is_premium=False,
            has_photo=False,
        )
    )


@pytest.mark.asyncio
async def test_reputation_get_score_default(session: AsyncSession) -> None:
    user = await create_telegram_user(session, suffix="default")
    service = ReputationService(session)

    score = await service.get_score(user.id)

    assert score == DEFAULT_TRUST_SCORE


@pytest.mark.asyncio
async def test_reputation_increase(session: AsyncSession) -> None:
    user = await create_telegram_user(session, suffix="inc")
    service = ReputationService(session)

    result = await service.increase(user.id, reason=ReputationChangeReason.MANUAL_APPROVED)

    assert result.old_score == DEFAULT_TRUST_SCORE
    assert result.new_score == 55.0
    assert await service.get_score(user.id) == 55.0


@pytest.mark.asyncio
async def test_reputation_decrease(session: AsyncSession) -> None:
    user = await create_telegram_user(session, suffix="dec")
    service = ReputationService(session)

    result = await service.decrease(user.id, reason=ReputationChangeReason.MANUAL_REJECTED)

    assert result.old_score == DEFAULT_TRUST_SCORE
    assert result.new_score == 40.0
    assert await service.get_score(user.id) == 40.0


@pytest.mark.asyncio
async def test_reputation_whitelist(session: AsyncSession) -> None:
    user = await create_telegram_user(session, suffix="wl")
    service = ReputationService(session)

    result = await service.set_whitelist(user.id)

    assert result.new_score == 100.0
    assert await service.get_score(user.id) == 100.0


@pytest.mark.asyncio
async def test_reputation_blacklist(session: AsyncSession) -> None:
    user = await create_telegram_user(session, suffix="bl")
    service = ReputationService(session)

    result = await service.set_blacklist(user.id)

    assert result.new_score == 0.0
    assert await service.get_score(user.id) == 0.0


@pytest.mark.asyncio
async def test_reputation_history_recorded(session: AsyncSession) -> None:
    user = await create_telegram_user(session, suffix="hist")
    service = ReputationService(session)
    history_repo = get_reputation_history_repository(session)

    await service.increase(user.id, reason=ReputationChangeReason.MANUAL_APPROVED)
    await service.decrease(user.id, reason=ReputationChangeReason.MANUAL_REJECTED)

    history = await history_repo.list_by_telegram_user_id(user.id)

    assert len(history) == 2
    reasons = {item.reason for item in history}
    assert reasons == {
        ReputationChangeReason.MANUAL_APPROVED,
        ReputationChangeReason.MANUAL_REJECTED,
    }
    assert await service.get_score(user.id) == 45.0


def test_reputation_engine_auto_thresholds() -> None:
    assert ReputationEngine.should_auto_approve(90.0) is True
    assert ReputationEngine.should_auto_approve(89.9) is False
    assert ReputationEngine.should_auto_reject(10.0) is True
    assert ReputationEngine.should_auto_reject(10.1) is False


def test_reputation_trend_calculation() -> None:
    user_id = uuid.uuid4()
    history = [
        ReputationHistory(
            telegram_user_id=user_id,
            old_score=50,
            new_score=60,
            reason=ReputationChangeReason.MANUAL_APPROVED,
            actor="admin_dashboard",
        ),
        ReputationHistory(
            telegram_user_id=user_id,
            old_score=45,
            new_score=50,
            reason=ReputationChangeReason.MANUAL_APPROVED,
            actor="admin_dashboard",
        ),
    ]

    assert ReputationService.calculate_trend(history) == ReputationTrend.UP

    history_down = [
        ReputationHistory(
            telegram_user_id=user_id,
            old_score=50,
            new_score=30,
            reason=ReputationChangeReason.MANUAL_REJECTED,
            actor="admin_dashboard",
        ),
        ReputationHistory(
            telegram_user_id=user_id,
            old_score=60,
            new_score=50,
            reason=ReputationChangeReason.MANUAL_REJECTED,
            actor="admin_dashboard",
        ),
    ]
    assert ReputationService.calculate_trend(history_down) == ReputationTrend.DOWN

    assert ReputationService.calculate_trend(history[:1]) == ReputationTrend.STABLE


@pytest.mark.asyncio
async def test_reputation_recalculate(session: AsyncSession) -> None:
    user = await create_telegram_user(session, suffix="recalc")
    reputation_repo = get_reputation_repository(session)
    service = ReputationService(session)

    reputation = await reputation_repo.get_or_create(user.id)
    reputation.reputation_score = 10.0
    await reputation_repo.update(reputation)

    await service.increase(user.id)
    await service.increase(user.id)

    history = await service.get_history(user.id)
    recalculated = await service.recalculate(user.id)

    assert recalculated == history[0].new_score
