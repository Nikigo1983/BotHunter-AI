from app.explainability import HybridExplainabilityBuilder


def _feature_set(
    *,
    has_photo: bool = False,
    has_username: bool = True,
    is_premium: bool = False,
    digit_count: int = 0,
    contains_dictionary_words: bool = False,
    contains_crypto_words: bool = False,
) -> dict:
    return {
        "profile": {
            "has_photo": has_photo,
            "has_username": has_username,
            "is_premium": is_premium,
            "language": "ru",
        },
        "username": {
            "digit_count": digit_count,
            "contains_dictionary_words": contains_dictionary_words,
            "contains_crypto_words": contains_crypto_words,
            "contains_random_sequence": False,
        },
        "name": {
            "contains_suspicious_words": False,
            "mixed_alphabet": False,
            "emoji_count": 0,
        },
    }


def test_hybrid_builder_adds_profile_positives() -> None:
    result = HybridExplainabilityBuilder.build(
        feature_set=_feature_set(has_photo=True, is_premium=True),
        trust_score=95.0,
        triggered_rules=[],
        rule_score=0.0,
    )

    assert "Есть фотография профиля" in result.positive_signals
    assert "Premium-аккаунт" in result.positive_signals
    assert "Репутация 95/100" in result.positive_signals


def test_hybrid_builder_adds_rule_and_feature_negatives() -> None:
    result = HybridExplainabilityBuilder.build(
        feature_set=_feature_set(has_photo=False, has_username=True, digit_count=3),
        trust_score=50.0,
        triggered_rules=[{"rule": "NoPhotoRule", "score": 20}],
        rule_score=20.0,
        ai_negative=["нет фото"],
    )

    assert "Нет фотографии профиля" in result.negative_signals
    assert "Username содержит цифры" in result.negative_signals
    assert "нет фото" not in result.negative_signals


def test_hybrid_builder_merges_ai_signals_without_duplicates() -> None:
    result = HybridExplainabilityBuilder.build(
        feature_set=_feature_set(has_photo=True, has_username=True),
        trust_score=80.0,
        triggered_rules=[],
        rule_score=0.0,
        ai_positive=["есть username"],
        ai_negative=["молодой аккаунт"],
    )

    assert "Есть читаемый username" in result.positive_signals
    assert "молодой аккаунт" in result.negative_signals
    assert result.positive_signals.count("Есть читаемый username") == 1


def test_hybrid_builder_trust_negative() -> None:
    result = HybridExplainabilityBuilder.build(
        feature_set=_feature_set(),
        trust_score=25.0,
        triggered_rules=[],
        rule_score=10.0,
    )

    assert "Низкая репутация (25/100)" in result.negative_signals


def test_risk_level_labels() -> None:
    assert HybridExplainabilityBuilder.risk_level(15.0) == "low"
    assert HybridExplainabilityBuilder.risk_level(48.0) == "medium"
    assert HybridExplainabilityBuilder.risk_level(82.0) == "high"
    assert HybridExplainabilityBuilder.risk_level_label(48.0) == "Средний риск"
