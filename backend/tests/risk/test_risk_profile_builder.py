import pytest

from app.features import FeatureExtractor
from app.models.telegram_user import TelegramUser
from app.risk import RiskLevel, RiskProfileBuilder
from app.rules.engine import RuleEngine, RuleEngineResult, TriggeredRule


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


def build_profile(**user_kwargs: object):
    features = FeatureExtractor().extract(make_user(**user_kwargs))
    rule_result = RuleEngine().evaluate(features)
    return RiskProfileBuilder().build(features, rule_result)


def test_risk_profile_low_for_clean_user() -> None:
    profile = build_profile()

    assert profile.risk_level == RiskLevel.LOW
    assert profile.confidence >= 0.9
    assert profile.signals == []
    assert "безопасным" in profile.summary.lower()
    assert "не обнаружено" in profile.main_reason.lower()


def test_risk_profile_medium_for_moderate_score() -> None:
    profile = build_profile(
        has_photo=False,
        username="user1234567",
        language_code=None,
    )

    assert profile.risk_level == RiskLevel.MEDIUM
    assert 0.0 <= profile.confidence <= 1.0
    assert "no_photo" in profile.signals
    assert "many_digits" in profile.signals
    assert "unknown_language" in profile.signals
    assert profile.main_reason


def test_risk_profile_high_for_risky_user() -> None:
    profile = build_profile(
        has_photo=False,
        username="crypto1234567",
        first_name="Crypto",
        last_name="Bonus",
        language_code=None,
    )

    assert profile.risk_level == RiskLevel.HIGH
    assert profile.confidence >= 0.5
    assert "crypto_keyword" in profile.signals
    assert "many_digits" in profile.signals
    assert len(profile.summary) > 0


def test_signals_random_username_and_mixed_alphabet() -> None:
    features = FeatureExtractor().extract(
        make_user(username="xqwpzvnmkjrt", first_name="Ivan", last_name="Иванов")
    )
    rule_result = RuleEngine().evaluate(features)
    profile = RiskProfileBuilder().build(features, rule_result)

    assert "random_username" in profile.signals
    assert "mixed_alphabet" in profile.signals


def test_signal_premium() -> None:
    features = FeatureExtractor().extract(make_user(is_premium=True))
    rule_result = RuleEngineResult(rule_score=0, triggered_rules=[])
    profile = RiskProfileBuilder().build(features, rule_result)

    assert "premium" in profile.signals
    assert profile.risk_level == RiskLevel.LOW


def test_signal_emoji_name() -> None:
    profile = build_profile(first_name="😀😁😂", last_name="Test")

    assert "emoji_name" in profile.signals
    assert "emoji" in profile.summary.lower() or "emoji" in profile.main_reason.lower()


def test_main_reason_uses_top_triggered_rule() -> None:
    features = FeatureExtractor().extract(make_user(first_name=None, last_name=None))
    rule_result = RuleEngine().evaluate(features)
    profile = RiskProfileBuilder().build(features, rule_result)

    assert profile.risk_level == RiskLevel.MEDIUM
    assert profile.main_reason == "Пустое имя пользователя"


def test_builder_with_manual_rule_result() -> None:
    features = FeatureExtractor().extract(make_user())
    rule_result = RuleEngineResult(
        rule_score=45,
        triggered_rules=[TriggeredRule(rule="NoPhotoRule", score=20)],
    )
    profile = RiskProfileBuilder().build(features, rule_result)

    assert profile.risk_level == RiskLevel.MEDIUM
    assert profile.main_reason == "Отсутствует фотография профиля"
