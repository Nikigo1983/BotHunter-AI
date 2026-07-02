from datetime import UTC, datetime

import pytest

from app.features.extractor import FeatureExtractor, EXTRACTION_VERSION
from app.features.utils import (
    calculate_entropy,
    calculate_uppercase_ratio,
    contains_random_sequence,
    contains_words,
    count_digits,
    count_emoji,
    get_display_name,
    has_mixed_alphabet,
    max_consecutive_digits,
    CYRILLIC_PATTERN,
    DICTIONARY_WORDS,
    FORBIDDEN_WORDS,
    LATIN_PATTERN,
)
from app.models.telegram_user import TelegramUser


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


@pytest.fixture
def extractor() -> FeatureExtractor:
    return FeatureExtractor()


def test_profile_features(extractor: FeatureExtractor) -> None:
    features = extractor.extract(
        make_user(has_photo=False, username=None, language_code=None, is_premium=True)
    )

    assert features.profile.has_photo is False
    assert features.profile.has_username is False
    assert features.profile.is_premium is True
    assert features.profile.language is None
    assert features.profile.account_created_today is False
    assert features.profile.has_linked_phone is True


def test_profile_account_age_features(extractor: FeatureExtractor) -> None:
    reference_time = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    features = extractor.extract(
        make_user(telegram_id=9_500_000_000, is_premium=False),
        reference_time=reference_time,
    )

    assert features.profile.account_created_today is True
    assert features.profile.has_linked_phone is False


def test_username_digit_features(extractor: FeatureExtractor) -> None:
    features = extractor.extract(make_user(username="abc12345xyz"))

    assert features.username.username_length == 11
    assert features.username.digit_count == 5
    assert features.username.consecutive_digits == 5


def test_username_dictionary_and_crypto_words(extractor: FeatureExtractor) -> None:
    dictionary = extractor.extract(make_user(username="official_support"))
    crypto = extractor.extract(make_user(username="crypto_bonus"))

    assert dictionary.username.contains_dictionary_words is True
    assert dictionary.username.contains_crypto_words is False
    assert crypto.username.contains_crypto_words is True


def test_username_entropy_and_random_sequence(extractor: FeatureExtractor) -> None:
    random_username = "xqwpzvnm"
    entropy = calculate_entropy(random_username)
    features = extractor.extract(make_user(username=random_username))

    assert features.username.entropy == round(entropy, 4)
    assert features.username.entropy > 2.5
    assert features.username.contains_random_sequence is contains_random_sequence(
        random_username,
        entropy,
    )


def test_name_length_and_emoji(extractor: FeatureExtractor) -> None:
    features = extractor.extract(make_user(first_name="😀😁😂", last_name="Test"))

    assert features.name.full_name_length == len("😀😁😂 Test")
    assert features.name.emoji_count == count_emoji("😀😁😂 Test")


def test_name_alphabet_ratios(extractor: FeatureExtractor) -> None:
    mixed = extractor.extract(make_user(first_name="Ivan", last_name="Иванов"))
    latin_only = extractor.extract(make_user(first_name="John", last_name="Smith"))

    assert mixed.name.mixed_alphabet is True
    assert mixed.name.latin_ratio > 0
    assert mixed.name.cyrillic_ratio > 0
    assert latin_only.name.mixed_alphabet is False
    assert latin_only.name.latin_ratio == pytest.approx(1.0)


def test_name_uppercase_ratio(extractor: FeatureExtractor) -> None:
    features = extractor.extract(make_user(first_name="IVAN", last_name="petrov"))
    assert features.name.uppercase_ratio == pytest.approx(
        calculate_uppercase_ratio("IVAN petrov")
    )


def test_name_suspicious_words(extractor: FeatureExtractor) -> None:
    features = extractor.extract(make_user(first_name="Crypto", last_name="Bonus"))
    assert features.name.contains_suspicious_words is True


def test_system_features(extractor: FeatureExtractor) -> None:
    features = extractor.extract(make_user())
    assert features.system.extraction_version == EXTRACTION_VERSION
    assert features.system.extracted_at is not None


def test_utils_get_display_name() -> None:
    assert get_display_name("Ivan", "Petrov") == "Ivan Petrov"
    assert get_display_name(None, None) == ""


def test_utils_count_digits_and_consecutive() -> None:
    assert count_digits("ab12cd345") == 5
    assert max_consecutive_digits("ab12345x") == 5


def test_utils_contains_words() -> None:
    assert contains_words("my_crypto_wallet", FORBIDDEN_WORDS) is True
    assert contains_words("official_help", DICTIONARY_WORDS) is True


def test_utils_calculate_entropy_empty() -> None:
    assert calculate_entropy("") == 0.0


def test_utils_mixed_alphabet() -> None:
    assert has_mixed_alphabet("Hello мир") is True
    assert has_mixed_alphabet("Hello world") is False


def test_utils_letter_ratios() -> None:
    from app.features.utils import calculate_letter_ratio

    assert calculate_letter_ratio("Ivan", LATIN_PATTERN) == 1.0
    assert calculate_letter_ratio("Иван", CYRILLIC_PATTERN) == 1.0
