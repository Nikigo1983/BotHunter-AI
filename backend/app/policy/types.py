from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.config.decision_settings import DecisionThresholds
from app.rules.definitions import (
    AccountCreatedTodayRule,
    EmptyNameRule,
    LongNameRule,
    NoLinkedPhoneRule,
    NoPhotoRule,
    NoUsernameRule,
    SuspiciousNameWordsRule,
    TooManyEmojiRule,
    UnknownLanguageRule,
    UsernameConsecutiveDigitsRule,
    UsernameManyDigitsRule,
)
from app.rules.engine import DEFAULT_RULES, RuleEngine

RULE_CLASS_MAP = {
    NoPhotoRule.__name__: NoPhotoRule,
    NoUsernameRule.__name__: NoUsernameRule,
    UsernameManyDigitsRule.__name__: UsernameManyDigitsRule,
    UsernameConsecutiveDigitsRule.__name__: UsernameConsecutiveDigitsRule,
    SuspiciousNameWordsRule.__name__: SuspiciousNameWordsRule,
    LongNameRule.__name__: LongNameRule,
    TooManyEmojiRule.__name__: TooManyEmojiRule,
    EmptyNameRule.__name__: EmptyNameRule,
    UnknownLanguageRule.__name__: UnknownLanguageRule,
    AccountCreatedTodayRule.__name__: AccountCreatedTodayRule,
    NoLinkedPhoneRule.__name__: NoLinkedPhoneRule,
}


@dataclass(slots=True)
class RulePolicyConfig:
    rule_key: str
    score: int
    enabled: bool = True
    description: str = ""
    admin_comment: str | None = None


@dataclass(slots=True)
class PolicyThresholdConfig:
    approve_below: int = 30
    reject_from: int = 70
    trust_auto_approve: int = 90
    trust_auto_reject: int = 10
    ai_threshold: float = 0.75

    def to_decision_thresholds(self) -> DecisionThresholds:
        return DecisionThresholds(
            approve_below=self.approve_below,
            reject_from=self.reject_from,
        )


@dataclass(slots=True)
class EffectivePolicy:
    version_id: uuid.UUID | None
    version_number: int
    author: str
    comment: str | None
    rules: dict[str, RulePolicyConfig] = field(default_factory=dict)
    thresholds: PolicyThresholdConfig = field(default_factory=PolicyThresholdConfig)

    def build_rule_engine(self) -> RuleEngine:
        return RuleEngine(build_rules_from_policy(self.rules))

    def build_decision_engine(self):
        from app.services.decision_engine import DecisionEngine

        return DecisionEngine(self.thresholds.to_decision_thresholds())

    def with_rule_override(
        self,
        rule_key: str,
        *,
        score: int | None = None,
        enabled: bool | None = None,
        description: str | None = None,
        admin_comment: str | None = None,
    ) -> EffectivePolicy:
        rules = dict(self.rules)
        current = rules[rule_key]
        rules[rule_key] = RulePolicyConfig(
            rule_key=rule_key,
            score=score if score is not None else current.score,
            enabled=enabled if enabled is not None else current.enabled,
            description=description if description is not None else current.description,
            admin_comment=admin_comment if admin_comment is not None else current.admin_comment,
        )
        return EffectivePolicy(
            version_id=self.version_id,
            version_number=self.version_number,
            author=self.author,
            comment=self.comment,
            rules=rules,
            thresholds=self.thresholds,
        )

    def with_thresholds(self, thresholds: PolicyThresholdConfig) -> EffectivePolicy:
        return EffectivePolicy(
            version_id=self.version_id,
            version_number=self.version_number,
            author=self.author,
            comment=self.comment,
            rules=self.rules,
            thresholds=thresholds,
        )


def build_default_rule_configs() -> dict[str, RulePolicyConfig]:
    configs: dict[str, RulePolicyConfig] = {}
    for rule_class in DEFAULT_RULES:
        instance = rule_class()
        configs[rule_class.__name__] = RulePolicyConfig(
            rule_key=rule_class.__name__,
            score=instance.default_weight(),
            enabled=True,
            description=instance.default_description(),
        )
    return configs


def build_default_thresholds() -> PolicyThresholdConfig:
    from app.config.decision_settings import get_decision_thresholds

    thresholds = get_decision_thresholds()
    return PolicyThresholdConfig(
        approve_below=thresholds.approve_below,
        reject_from=thresholds.reject_from,
    )


def build_rules_from_policy(rules: dict[str, RulePolicyConfig]) -> list:
    built = []
    for rule_class in DEFAULT_RULES:
        key = rule_class.__name__
        config = rules.get(key)
        if config is None:
            built.append(rule_class())
            continue
        built.append(
            rule_class(
                score=config.score,
                enabled=config.enabled,
                description_override=config.description,
            )
        )
    return built
