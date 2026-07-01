import uuid

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.join_request import JoinRequest
from app.models.policy_rule_config import PolicyRuleConfig as PolicyRuleConfigModel
from app.models.policy_threshold_config import PolicyThresholdConfigModel
from app.models.policy_version import PolicyVersion
from app.models.telegram_user import TelegramUser
from app.policy.types import PolicyThresholdConfig, RulePolicyConfig
from app.repositories.base import BaseRepository


class PolicyRepository(BaseRepository[PolicyVersion]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PolicyVersion)

    async def get_current_version(self) -> PolicyVersion | None:
        stmt = (
            select(PolicyVersion)
            .where(PolicyVersion.is_current.is_(True))
            .order_by(desc(PolicyVersion.version_number))
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_version_number(self, version_number: int) -> PolicyVersion | None:
        stmt = select(PolicyVersion).where(PolicyVersion.version_number == version_number)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, version_id: uuid.UUID) -> PolicyVersion | None:
        return await super().get_by_id(version_id)

    async def list_versions(self, *, limit: int = 50) -> list[PolicyVersion]:
        stmt = select(PolicyVersion).order_by(desc(PolicyVersion.version_number)).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_next_version_number(self) -> int:
        stmt = select(func.coalesce(func.max(PolicyVersion.version_number), 0))
        current = int((await self._session.execute(stmt)).scalar_one())
        return current + 1

    async def clear_current_flags(self) -> None:
        stmt = update(PolicyVersion).values(is_current=False).where(PolicyVersion.is_current.is_(True))
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_rule_configs(self, version_id: uuid.UUID) -> list[PolicyRuleConfigModel]:
        stmt = (
            select(PolicyRuleConfigModel)
            .where(PolicyRuleConfigModel.version_id == version_id)
            .order_by(PolicyRuleConfigModel.rule_key.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_threshold_config(self, version_id: uuid.UUID) -> PolicyThresholdConfigModel | None:
        stmt = select(PolicyThresholdConfigModel).where(
            PolicyThresholdConfigModel.version_id == version_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create_version_with_snapshots(
        self,
        *,
        author: str,
        comment: str | None,
        rules: dict[str, RulePolicyConfig],
        thresholds: PolicyThresholdConfig,
        make_current: bool = True,
    ) -> PolicyVersion:
        if make_current:
            await self.clear_current_flags()
        version_number = await self.get_next_version_number()
        version = PolicyVersion(
            version_number=version_number,
            author=author,
            comment=comment,
            is_current=make_current,
        )
        await self.create(version)
        for rule_key, config in rules.items():
            self._session.add(
                PolicyRuleConfigModel(
                    version_id=version.id,
                    rule_key=rule_key,
                    score=config.score,
                    enabled=config.enabled,
                    description=config.description,
                    admin_comment=config.admin_comment,
                )
            )
        self._session.add(
            PolicyThresholdConfigModel(
                version_id=version.id,
                approve_below=thresholds.approve_below,
                reject_from=thresholds.reject_from,
                trust_auto_approve=thresholds.trust_auto_approve,
                trust_auto_reject=thresholds.trust_auto_reject,
                ai_threshold=thresholds.ai_threshold,
            )
        )
        await self._session.flush()
        await self._session.refresh(version)
        return version

    async def get_recent_join_cases(self, *, limit: int = 100) -> list[tuple[JoinRequest, TelegramUser]]:
        stmt = (
            select(JoinRequest, TelegramUser)
            .join(TelegramUser, TelegramUser.id == JoinRequest.telegram_user_id)
            .order_by(desc(JoinRequest.created_at))
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).all())

    async def find_rule_last_change(self, rule_key: str) -> PolicyVersion | None:
        stmt = (
            select(PolicyVersion)
            .join(PolicyRuleConfigModel, PolicyRuleConfigModel.version_id == PolicyVersion.id)
            .where(PolicyRuleConfigModel.rule_key == rule_key)
            .order_by(desc(PolicyVersion.version_number))
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
