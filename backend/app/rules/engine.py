from dataclasses import asdict, dataclass
from typing import Any

from app.features.feature_set import FeatureSet
from app.rules.base import BaseRule
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


@dataclass(slots=True)
class TriggeredRule:
    rule: str
    score: int


@dataclass(slots=True)
class RuleEngineResult:
    rule_score: int
    triggered_rules: list[TriggeredRule]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_score": self.rule_score,
            "triggered_rules": [asdict(item) for item in self.triggered_rules],
        }


DEFAULT_RULES: tuple[type[BaseRule], ...] = (
    NoPhotoRule,
    NoUsernameRule,
    UsernameManyDigitsRule,
    UsernameConsecutiveDigitsRule,
    SuspiciousNameWordsRule,
    LongNameRule,
    TooManyEmojiRule,
    EmptyNameRule,
    UnknownLanguageRule,
    AccountCreatedTodayRule,
    NoLinkedPhoneRule,
)


class RuleEngine:
    def __init__(self, rules: list[BaseRule] | None = None) -> None:
        self._rules = rules or [rule_class() for rule_class in DEFAULT_RULES]

    def evaluate(self, features: FeatureSet) -> RuleEngineResult:
        triggered_rules: list[TriggeredRule] = []
        total_score = 0

        for rule in self._rules:
            score = rule.calculate(features)
            if score <= 0:
                continue
            triggered_rules.append(TriggeredRule(rule=rule.name, score=score))
            total_score += score

        return RuleEngineResult(
            rule_score=total_score,
            triggered_rules=triggered_rules,
        )

    def evaluate_as_json(self, features: FeatureSet) -> dict[str, Any]:
        return self.evaluate(features).to_dict()
