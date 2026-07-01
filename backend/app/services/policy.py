import uuid
from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.policy.types import (
    EffectivePolicy,
    PolicyThresholdConfig,
    RulePolicyConfig,
    build_default_rule_configs,
    build_default_thresholds,
)
from app.repositories.analytics import AnalyticsRepository
from app.repositories.deps import get_audit_log_repository, get_policy_repository


@dataclass(slots=True)
class RulePolicyView:
    rule_key: str
    name: str
    description: str
    score: int
    enabled: bool
    triggered_count: int
    accuracy: float | None
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None
    false_positive_rate: float | None
    false_negative_rate: float | None
    last_changed_at: datetime | None
    last_changed_by: str | None
    admin_comment: str | None


@dataclass(slots=True)
class PolicyVersionView:
    id: uuid.UUID
    version_number: int
    author: str
    comment: str | None
    created_at: datetime
    is_current: bool
    changed_rules: list[str]


@dataclass(slots=True)
class PolicyComparisonView:
    current_version: int
    previous_version: int
    rule_changes: list[dict]
    threshold_changes: list[dict]


class PolicyService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> None:
        self._session = session
        self._organization_id = organization_id
        self._workspace_id = workspace_id
        self._user_id = user_id
        self._repo = get_policy_repository(session)
        self._audit_repo = get_audit_log_repository(session)

    async def _resolve_organization_id(self) -> uuid.UUID:
        if self._organization_id is not None:
            return self._organization_id
        from app.repositories.deps import get_organization_repository

        org = await get_organization_repository(self._session).get_by_slug("default")
        if org is None:
            raise RuntimeError("Default organization is not bootstrapped")
        self._organization_id = org.id
        return org.id

    async def ensure_initial_policy(self, organization_id: uuid.UUID | None = None) -> None:
        org_id = organization_id or await self._resolve_organization_id()
        current = await self._repo.get_current_version(org_id)
        if current is not None:
            return
        await self._repo.create_version_with_snapshots(
            organization_id=org_id,
            author="system",
            comment="Initial policy from Rule Engine defaults",
            rules=build_default_rule_configs(),
            thresholds=build_default_thresholds(),
            make_current=True,
        )

    async def get_effective_policy(self, version_id: uuid.UUID | None = None) -> EffectivePolicy:
        org_id = await self._resolve_organization_id()
        await self.ensure_initial_policy(org_id)
        if version_id is not None:
            version = await self._repo.get_by_id(version_id)
            if version is not None and version.organization_id != org_id:
                raise ValueError("Policy version belongs to another organization")
        else:
            version = await self._repo.get_current_version(org_id)
        if version is None:
            return EffectivePolicy(
                version_id=None,
                version_number=0,
                author="system",
                comment=None,
                rules=build_default_rule_configs(),
                thresholds=build_default_thresholds(),
            )
        return await self._build_effective_policy(version)

    async def list_rules(self) -> list[RulePolicyView]:
        policy = await self.get_effective_policy()
        org_id = await self._resolve_organization_id()
        analytics_repo = AnalyticsRepository(
            self._session,
            organization_id=org_id,
            workspace_id=self._workspace_id,
        )
        analytics_map = {
            row["rule_name"]: row for row in await analytics_repo.get_rule_effectiveness_raw()
        }
        views: list[RulePolicyView] = []
        for rule_key, config in policy.rules.items():
            stats = analytics_map.get(rule_key, {})
            triggered = int(stats.get("triggered_count", 0))
            false_positives = int(stats.get("false_positive_count", 0))
            ai_agreed = int(stats.get("ai_agreed_count", 0))
            admin_agreed = int(stats.get("admin_agreed_count", 0))
            precision = None
            recall = None
            accuracy = None
            fpr = None
            fnr = None
            if triggered > 0:
                precision = round((triggered - false_positives) / triggered, 4)
                fpr = round(false_positives / triggered, 4)
                accuracy = precision
            positive_signal = ai_agreed + admin_agreed
            if positive_signal > 0:
                recall = round(positive_signal / max(triggered, 1), 4)
                fnr = round(max(0, triggered - positive_signal) / max(triggered, 1), 4)
            last_version = await self._repo.find_rule_last_change(await self._resolve_organization_id(), rule_key)
            views.append(
                RulePolicyView(
                    rule_key=rule_key,
                    name=rule_key,
                    description=config.description,
                    score=config.score,
                    enabled=config.enabled,
                    triggered_count=triggered,
                    accuracy=accuracy,
                    false_positives=false_positives,
                    false_negatives=max(0, triggered - positive_signal),
                    precision=precision,
                    recall=recall,
                    false_positive_rate=fpr,
                    false_negative_rate=fnr,
                    last_changed_at=last_version.created_at if last_version else None,
                    last_changed_by=last_version.author if last_version else None,
                    admin_comment=config.admin_comment,
                )
            )
        return views

    async def get_rule(self, rule_key: str) -> RulePolicyView | None:
        rules = await self.list_rules()
        return next((item for item in rules if item.rule_key == rule_key), None)

    async def update_rule(
        self,
        rule_key: str,
        *,
        score: int,
        enabled: bool,
        description: str,
        admin_comment: str | None,
        author: str,
    ) -> EffectivePolicy:
        current = await self.get_effective_policy()
        if rule_key not in current.rules:
            raise ValueError(f"Unknown rule: {rule_key}")
        rules = dict(current.rules)
        rules[rule_key] = RulePolicyConfig(
            rule_key=rule_key,
            score=score,
            enabled=enabled,
            description=description,
            admin_comment=admin_comment,
        )
        org_id = await self._resolve_organization_id()
        version = await self._repo.create_version_with_snapshots(
            organization_id=org_id,
            author=author,
            comment=f"Updated rule {rule_key}",
            rules=rules,
            thresholds=current.thresholds,
        )
        await self._audit(author, "policy_rule_updated", version.id, {"rule_key": rule_key})
        return await self._build_effective_policy(version)

    async def update_thresholds(
        self,
        *,
        approve_below: int,
        reject_from: int,
        trust_auto_approve: int,
        trust_auto_reject: int,
        ai_threshold: float,
        author: str,
        comment: str | None = None,
    ) -> EffectivePolicy:
        current = await self.get_effective_policy()
        thresholds = PolicyThresholdConfig(
            approve_below=approve_below,
            reject_from=reject_from,
            trust_auto_approve=trust_auto_approve,
            trust_auto_reject=trust_auto_reject,
            ai_threshold=ai_threshold,
        )
        org_id = await self._resolve_organization_id()
        version = await self._repo.create_version_with_snapshots(
            organization_id=org_id,
            author=author,
            comment=comment or "Updated global thresholds",
            rules=current.rules,
            thresholds=thresholds,
        )
        await self._audit(author, "policy_thresholds_updated", version.id, asdict(thresholds))
        return await self._build_effective_policy(version)

    async def rollback(self, version_id: uuid.UUID, *, author: str) -> EffectivePolicy:
        source = await self._repo.get_by_id(version_id)
        if source is None:
            raise ValueError("Policy version not found")
        if source.organization_id != await self._resolve_organization_id():
            raise ValueError("Policy version belongs to another organization")
        rules = await self._load_rules_dict(source.id)
        thresholds = await self._load_thresholds(source.id)
        org_id = await self._resolve_organization_id()
        version = await self._repo.create_version_with_snapshots(
            organization_id=org_id,
            author=author,
            comment=f"Rollback to policy v{source.version_number}",
            rules=rules,
            thresholds=thresholds,
        )
        await self._audit(
            author,
            "policy_rollback",
            version.id,
            {"from_version": source.version_number},
        )
        return await self._build_effective_policy(version)

    async def list_history(self, *, limit: int = 50) -> list[PolicyVersionView]:
        org_id = await self._resolve_organization_id()
        versions = await self._repo.list_versions(org_id, limit=limit)
        result: list[PolicyVersionView] = []
        for index, version in enumerate(versions):
            changed_rules: list[str] = []
            if index + 1 < len(versions):
                current_rules = {row.rule_key: row for row in await self._repo.get_rule_configs(version.id)}
                previous_rules = {
                    row.rule_key: row for row in await self._repo.get_rule_configs(versions[index + 1].id)
                }
                for key, row in current_rules.items():
                    prev = previous_rules.get(key)
                    if prev is None or prev.score != row.score or prev.enabled != row.enabled:
                        changed_rules.append(key)
            result.append(
                PolicyVersionView(
                    id=version.id,
                    version_number=version.version_number,
                    author=version.author,
                    comment=version.comment,
                    created_at=version.created_at,
                    is_current=version.is_current,
                    changed_rules=changed_rules,
                )
            )
        return result

    async def compare_versions(
        self,
        current_version_id: uuid.UUID | None = None,
        previous_version_id: uuid.UUID | None = None,
    ) -> PolicyComparisonView:
        org_id = await self._resolve_organization_id()
        await self.ensure_initial_policy(org_id)
        versions = await self._repo.list_versions(org_id, limit=2)
        if not versions:
            raise ValueError("No policy versions found")
        current = (
            await self._repo.get_by_id(current_version_id)
            if current_version_id
            else versions[0]
        )
        previous = (
            await self._repo.get_by_id(previous_version_id)
            if previous_version_id
            else (versions[1] if len(versions) > 1 else None)
        )
        if current is None or previous is None:
            raise ValueError("Unable to compare policy versions")
        current_rules = {row.rule_key: row for row in await self._repo.get_rule_configs(current.id)}
        previous_rules = {row.rule_key: row for row in await self._repo.get_rule_configs(previous.id)}
        rule_changes = []
        for key, row in current_rules.items():
            prev = previous_rules.get(key)
            if prev is None:
                continue
            if prev.score != row.score or prev.enabled != row.enabled or prev.description != row.description:
                rule_changes.append(
                    {
                        "rule_key": key,
                        "score": {"from": prev.score, "to": row.score},
                        "enabled": {"from": prev.enabled, "to": row.enabled},
                    }
                )
        current_thresholds = await self._repo.get_threshold_config(current.id)
        previous_thresholds = await self._repo.get_threshold_config(previous.id)
        threshold_changes = []
        if current_thresholds and previous_thresholds:
            for field in (
                "approve_below",
                "reject_from",
                "trust_auto_approve",
                "trust_auto_reject",
                "ai_threshold",
            ):
                old = getattr(previous_thresholds, field)
                new = getattr(current_thresholds, field)
                if old != new:
                    threshold_changes.append({"field": field, "from": old, "to": new})
        return PolicyComparisonView(
            current_version=current.version_number,
            previous_version=previous.version_number,
            rule_changes=rule_changes,
            threshold_changes=threshold_changes,
        )

    async def _build_effective_policy(self, version) -> EffectivePolicy:
        rules = await self._load_rules_dict(version.id)
        thresholds = await self._load_thresholds(version.id)
        return EffectivePolicy(
            version_id=version.id,
            version_number=version.version_number,
            author=version.author,
            comment=version.comment,
            rules=rules,
            thresholds=thresholds,
        )

    async def _load_rules_dict(self, version_id: uuid.UUID) -> dict[str, RulePolicyConfig]:
        rows = await self._repo.get_rule_configs(version_id)
        return {
            row.rule_key: RulePolicyConfig(
                rule_key=row.rule_key,
                score=row.score,
                enabled=row.enabled,
                description=row.description,
                admin_comment=row.admin_comment,
            )
            for row in rows
        }

    async def _load_thresholds(self, version_id: uuid.UUID) -> PolicyThresholdConfig:
        row = await self._repo.get_threshold_config(version_id)
        if row is None:
            return build_default_thresholds()
        return PolicyThresholdConfig(
            approve_below=row.approve_below,
            reject_from=row.reject_from,
            trust_auto_approve=row.trust_auto_approve,
            trust_auto_reject=row.trust_auto_reject,
            ai_threshold=row.ai_threshold,
        )

    async def _audit(self, actor: str, action: str, version_id: uuid.UUID, details: dict) -> None:
        import json

        await self._audit_repo.create(
            AuditLog(
                actor=actor,
                organization_id=self._organization_id,
                workspace_id=self._workspace_id,
                user_id=self._user_id,
                action=action,
                entity="policy_version",
                entity_id=version_id,
                details=json.dumps(details, ensure_ascii=False, default=str),
            )
        )
