from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ProfileFeatures:
    has_photo: bool
    has_username: bool
    is_premium: bool
    language: str | None
    account_created_today: bool
    has_linked_phone: bool | None


@dataclass(slots=True)
class UsernameFeatures:
    username_length: int
    digit_count: int
    consecutive_digits: int
    contains_dictionary_words: bool
    contains_crypto_words: bool
    contains_random_sequence: bool
    entropy: float


@dataclass(slots=True)
class NameFeatures:
    full_name_length: int
    emoji_count: int
    uppercase_ratio: float
    latin_ratio: float
    cyrillic_ratio: float
    mixed_alphabet: bool
    contains_suspicious_words: bool


@dataclass(slots=True)
class SystemFeatures:
    extraction_version: str
    extracted_at: datetime


@dataclass(slots=True)
class FeatureSet:
    profile: ProfileFeatures
    username: UsernameFeatures
    name: NameFeatures
    system: SystemFeatures

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
