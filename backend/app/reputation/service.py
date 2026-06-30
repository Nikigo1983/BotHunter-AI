import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reputation_history import ReputationHistory
from app.repositories.deps import get_reputation_history_repository, get_reputation_repository
from app.reputation.engine import DEFAULT_TRUST_SCORE, ReputationEngine
from app.reputation.enums import ReputationChangeReason, ReputationTrend


@dataclass(slots=True)
class ReputationUpdateResult:
    old_score: float
    new_score: float
    reason: ReputationChangeReason


class ReputationService:
    ACTOR_ADMIN = "admin_dashboard"
    ACTOR_SYSTEM = "system"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._reputation_repo = get_reputation_repository(session)
        self._history_repo = get_reputation_history_repository(session)
        self._engine = ReputationEngine()

    async def get_score(self, telegram_user_id: uuid.UUID) -> float:
        reputation = await self._reputation_repo.get_or_create(telegram_user_id)
        return reputation.reputation_score

    async def increase(
        self,
        telegram_user_id: uuid.UUID,
        *,
        reason: ReputationChangeReason = ReputationChangeReason.MANUAL_APPROVED,
        actor: str = ACTOR_ADMIN,
    ) -> ReputationUpdateResult:
        return await self._apply_score_change(
            telegram_user_id,
            new_score=self._engine.increase(await self.get_score(telegram_user_id)),
            reason=reason,
            actor=actor,
        )

    async def decrease(
        self,
        telegram_user_id: uuid.UUID,
        *,
        reason: ReputationChangeReason = ReputationChangeReason.MANUAL_REJECTED,
        actor: str = ACTOR_ADMIN,
    ) -> ReputationUpdateResult:
        return await self._apply_score_change(
            telegram_user_id,
            new_score=self._engine.decrease(await self.get_score(telegram_user_id)),
            reason=reason,
            actor=actor,
        )

    async def set_whitelist(
        self,
        telegram_user_id: uuid.UUID,
        *,
        actor: str = ACTOR_ADMIN,
    ) -> ReputationUpdateResult:
        return await self._apply_score_change(
            telegram_user_id,
            new_score=self._engine.set_whitelist(),
            reason=ReputationChangeReason.WHITELISTED,
            actor=actor,
        )

    async def set_blacklist(
        self,
        telegram_user_id: uuid.UUID,
        *,
        actor: str = ACTOR_ADMIN,
    ) -> ReputationUpdateResult:
        return await self._apply_score_change(
            telegram_user_id,
            new_score=self._engine.set_blacklist(),
            reason=ReputationChangeReason.BLACKLISTED,
            actor=actor,
        )

    async def recalculate(self, telegram_user_id: uuid.UUID) -> float:
        history = await self._history_repo.list_by_telegram_user_id(telegram_user_id, limit=1000)
        if not history:
            return await self.get_score(telegram_user_id)

        score = history[0].new_score
        reputation = await self._reputation_repo.get_or_create(telegram_user_id)
        reputation.reputation_score = score
        await self._reputation_repo.update(reputation)
        return score

    async def get_history(
        self,
        telegram_user_id: uuid.UUID,
        *,
        limit: int = 50,
    ) -> list[ReputationHistory]:
        return await self._history_repo.list_by_telegram_user_id(telegram_user_id, limit=limit)

    @staticmethod
    def calculate_trend(history: list[ReputationHistory]) -> ReputationTrend:
        if len(history) < 2:
            return ReputationTrend.STABLE

        recent = history[:3]
        delta = recent[0].new_score - recent[-1].new_score
        if delta > 0.5:
            return ReputationTrend.UP
        if delta < -0.5:
            return ReputationTrend.DOWN
        return ReputationTrend.STABLE

    async def _apply_score_change(
        self,
        telegram_user_id: uuid.UUID,
        *,
        new_score: float,
        reason: ReputationChangeReason,
        actor: str,
    ) -> ReputationUpdateResult:
        reputation = await self._reputation_repo.get_or_create(telegram_user_id)
        old_score = reputation.reputation_score
        if old_score == new_score:
            return ReputationUpdateResult(old_score=old_score, new_score=new_score, reason=reason)

        reputation.reputation_score = new_score
        await self._reputation_repo.update(reputation)
        await self._history_repo.create(
            ReputationHistory(
                telegram_user_id=telegram_user_id,
                old_score=old_score,
                new_score=new_score,
                reason=reason,
                actor=actor,
            )
        )
        return ReputationUpdateResult(old_score=old_score, new_score=new_score, reason=reason)
