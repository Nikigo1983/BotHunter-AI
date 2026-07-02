from datetime import UTC, datetime

from app.features.telegram_account import (
    infer_has_linked_phone,
    is_account_created_on_date,
)
from app.features.feature_set import (
    FeatureSet,
    NameFeatures,
    ProfileFeatures,
    SystemFeatures,
    UsernameFeatures,
)
from app.features.utils import (
    calculate_entropy,
    calculate_letter_ratio,
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

EXTRACTION_VERSION = "1.1.0"


class FeatureExtractor:
    def extract(
        self,
        user: TelegramUser,
        *,
        reference_time: datetime | None = None,
    ) -> FeatureSet:
        now = reference_time or datetime.now(UTC)
        username = (user.username or "").strip()
        full_name = get_display_name(user.first_name, user.last_name)
        language = (user.language_code or "").strip() or None
        username_entropy = calculate_entropy(username)

        return FeatureSet(
            profile=ProfileFeatures(
                has_photo=user.has_photo,
                has_username=bool(username),
                is_premium=user.is_premium,
                language=language,
                account_created_today=is_account_created_on_date(
                    user.telegram_id,
                    reference_time=now,
                ),
                has_linked_phone=infer_has_linked_phone(
                    is_premium=user.is_premium,
                    telegram_id=user.telegram_id,
                    reference_time=now,
                ),
            ),
            username=UsernameFeatures(
                username_length=len(username),
                digit_count=count_digits(username),
                consecutive_digits=max_consecutive_digits(username),
                contains_dictionary_words=contains_words(username, DICTIONARY_WORDS),
                contains_crypto_words=contains_words(username, FORBIDDEN_WORDS),
                contains_random_sequence=contains_random_sequence(username, username_entropy),
                entropy=round(username_entropy, 4),
            ),
            name=NameFeatures(
                full_name_length=len(full_name),
                emoji_count=count_emoji(full_name),
                uppercase_ratio=round(calculate_uppercase_ratio(full_name), 4),
                latin_ratio=round(calculate_letter_ratio(full_name, LATIN_PATTERN), 4),
                cyrillic_ratio=round(calculate_letter_ratio(full_name, CYRILLIC_PATTERN), 4),
                mixed_alphabet=has_mixed_alphabet(full_name),
                contains_suspicious_words=contains_words(full_name, FORBIDDEN_WORDS),
            ),
            system=SystemFeatures(
                extraction_version=EXTRACTION_VERSION,
                extracted_at=now,
            ),
        )
