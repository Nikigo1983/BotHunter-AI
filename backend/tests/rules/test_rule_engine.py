import pytest

from app.features import FeatureExtractor
from app.models.telegram_user import TelegramUser
from app.rules.definitions import (
    EmptyNameRule,
    LongNameRule,
    NoPhotoRule,
    NoUsernameRule,
    SuspiciousNameWordsRule,
    TooManyEmojiRule,
    UnknownLanguageRule,
    UsernameConsecutiveDigitsRule,
    UsernameManyDigitsRule,
)
from app.rules.engine import RuleEngine


def make_user(**kwargs: object) -> TelegramUser:
    defaults = {
        "telegram_id": 10001,
        "username": "normal_user",
        "first_name": "Ivan",
        "last_name": "Petrov",
        "language_code": "ru",
        "is_premium": False,
        "has_photo": True,
    }
    defaults.update(kwargs)
    return TelegramUser(**defaults)  # type: ignore[arg-type]


def extract(**kwargs: object):
    return FeatureExtractor().extract(make_user(**kwargs))


@pytest.mark.parametrize(
    ("rule_cls", "user_kwargs", "expected_score"),
    [
        (NoPhotoRule, {"has_photo": False}, 20),
        (NoPhotoRule, {"has_photo": True}, 0),
        (NoUsernameRule, {"username": None}, 10),
        (NoUsernameRule, {"username": "   "}, 10),
        (NoUsernameRule, {"username": "valid_user"}, 0),
        (UsernameManyDigitsRule, {"username": "user1234567"}, 15),
        (UsernameManyDigitsRule, {"username": "user123456"}, 0),
        (UsernameConsecutiveDigitsRule, {"username": "abc12345x"}, 20),
        (UsernameConsecutiveDigitsRule, {"username": "abc1234x"}, 0),
        (SuspiciousNameWordsRule, {"first_name": "Crypto", "last_name": "King"}, 20),
        (SuspiciousNameWordsRule, {"first_name": "Ivan", "last_name": "Petrov"}, 0),
        (LongNameRule, {"first_name": "A" * 31, "last_name": None}, 10),
        (LongNameRule, {"first_name": "A" * 30, "last_name": None}, 0),
        (
            TooManyEmojiRule,
            {"first_name": "😀😁😂", "last_name": "Test"},
            15,
        ),
        (TooManyEmojiRule, {"first_name": "😀😁", "last_name": "Test"}, 0),
        (EmptyNameRule, {"first_name": None, "last_name": None}, 30),
        (EmptyNameRule, {"first_name": "Ivan"}, 0),
        (UnknownLanguageRule, {"language_code": None}, 5),
        (UnknownLanguageRule, {"language_code": "en"}, 0),
    ],
)
def test_individual_rules(rule_cls, user_kwargs, expected_score) -> None:
    rule = rule_cls()
    features = extract(**user_kwargs)
    assert rule.calculate(features) == expected_score
    assert rule.weight() == expected_score or expected_score == 0
    assert rule.description()


def test_suspicious_words_are_case_insensitive() -> None:
    rule = SuspiciousNameWordsRule()
    features = extract(first_name="Best", last_name="AIRDROP")
    assert rule.calculate(features) == 20


def test_username_without_value_does_not_trigger_digit_rules() -> None:
    features = extract(username=None)
    assert UsernameManyDigitsRule().calculate(features) == 0
    assert UsernameConsecutiveDigitsRule().calculate(features) == 0


def test_rule_engine_returns_zero_for_clean_user() -> None:
    engine = RuleEngine()
    result = engine.evaluate_as_json(extract())

    assert result == {"rule_score": 0, "triggered_rules": []}


def test_rule_engine_applies_multiple_rules() -> None:
    engine = RuleEngine()
    features = extract(
        has_photo=False,
        username="bot1234567",
        first_name="😀😁😂",
        last_name="",
        language_code=None,
    )
    result = engine.evaluate_as_json(features)

    assert result["rule_score"] == 20 + 15 + 20 + 15 + 5
    triggered_names = {item["rule"] for item in result["triggered_rules"]}
    assert triggered_names == {
        "NoPhotoRule",
        "UsernameManyDigitsRule",
        "UsernameConsecutiveDigitsRule",
        "TooManyEmojiRule",
        "UnknownLanguageRule",
    }


def test_rule_engine_example_like_payload() -> None:
    engine = RuleEngine()
    features = extract(has_photo=False, username="1234567abc")
    result = engine.evaluate_as_json(features)

    assert result["rule_score"] == 55
    assert result["triggered_rules"] == [
        {"rule": "NoPhotoRule", "score": 20},
        {"rule": "UsernameManyDigitsRule", "score": 15},
        {"rule": "UsernameConsecutiveDigitsRule", "score": 20},
    ]


def test_rule_engine_boundary_exact_thresholds() -> None:
    engine = RuleEngine()

    six_digits_user = extract(username="12ab34cd56ef")
    seven_digits_user = extract(username="12ab34cd56ef7")
    four_in_row_user = extract(username="x1234y")
    five_in_row_user = extract(username="x12345y")

    assert engine.evaluate(six_digits_user).rule_score == 0
    assert engine.evaluate(seven_digits_user).rule_score == 15
    assert engine.evaluate(four_in_row_user).rule_score == 0
    assert engine.evaluate(five_in_row_user).rule_score == 20
