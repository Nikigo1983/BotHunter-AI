from dataclasses import dataclass
from typing import Any

from app.features.feature_set import FeatureSet
from app.rules.base import TOO_MANY_EMOJI_THRESHOLD
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


@dataclass(slots=True)
class RuleInspectionItem:
    rule: str
    condition: str
    description: str
    matched: bool
    contribution: int


RULE_CONDITIONS: dict[str, str] = {
    "NoPhotoRule": "has_photo == false",
    "NoUsernameRule": "has_username == false",
    "UsernameManyDigitsRule": "username.digit_count > 6",
    "UsernameConsecutiveDigitsRule": "username.consecutive_digits > 4",
    "SuspiciousNameWordsRule": "name.contains_suspicious_words == true",
    "LongNameRule": "name.full_name_length > 30",
    "TooManyEmojiRule": f"name.emoji_count >= {TOO_MANY_EMOJI_THRESHOLD}",
    "EmptyNameRule": "name.full_name_length == 0",
    "UnknownLanguageRule": "profile.language is null",
    "AccountCreatedTodayRule": "profile.account_created_today == true",
    "NoLinkedPhoneRule": "profile.has_linked_phone == false",
}


class RuleInspector:
    def __init__(self, rule_engine: RuleEngine | None = None) -> None:
        self._rules = rule_engine._rules if rule_engine else [cls() for cls in DEFAULT_RULES]

    def inspect(self, features: FeatureSet) -> list[RuleInspectionItem]:
        triggered = {item.rule: item.score for item in self._rule_engine_evaluate(features)}
        items: list[RuleInspectionItem] = []
        for rule in self._rules:
            score = rule.calculate(features)
            items.append(
                RuleInspectionItem(
                    rule=rule.name,
                    condition=RULE_CONDITIONS.get(rule.name, rule.description()),
                    description=rule.description(),
                    matched=score > 0,
                    contribution=triggered.get(rule.name, 0),
                )
            )
        return items

    def _rule_engine_evaluate(self, features: FeatureSet):
        engine = RuleEngine(self._rules)
        return engine.evaluate(features).triggered_rules

    @staticmethod
    def to_dict(items: list[RuleInspectionItem]) -> list[dict[str, Any]]:
        return [
            {
                "rule": item.rule,
                "condition": item.condition,
                "description": item.description,
                "matched": item.matched,
                "contribution": item.contribution,
            }
            for item in items
        ]
