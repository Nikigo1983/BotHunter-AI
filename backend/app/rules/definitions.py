from app.features.feature_set import FeatureSet
from app.rules.base import TOO_MANY_EMOJI_THRESHOLD, BaseRule


class NoPhotoRule(BaseRule):
    def calculate(self, features: FeatureSet) -> int:
        if not self._enabled:
            return 0
        return self.weight() if not features.profile.has_photo else 0

    def default_description(self) -> str:
        return "Нет фотографии профиля"

    def default_weight(self) -> int:
        return 20


class NoUsernameRule(BaseRule):
    def calculate(self, features: FeatureSet) -> int:
        if not self._enabled:
            return 0
        return self.weight() if not features.profile.has_username else 0

    def default_description(self) -> str:
        return "Username отсутствует"

    def default_weight(self) -> int:
        return 10


class UsernameManyDigitsRule(BaseRule):
    def calculate(self, features: FeatureSet) -> int:
        if not self._enabled or not features.profile.has_username:
            return 0
        return self.weight() if features.username.digit_count > 6 else 0

    def default_description(self) -> str:
        return "Username содержит более 6 цифр"

    def default_weight(self) -> int:
        return 15


class UsernameConsecutiveDigitsRule(BaseRule):
    def calculate(self, features: FeatureSet) -> int:
        if not self._enabled or not features.profile.has_username:
            return 0
        return self.weight() if features.username.consecutive_digits > 4 else 0

    def default_description(self) -> str:
        return "Username содержит подряд более 4 цифр"

    def default_weight(self) -> int:
        return 20


class SuspiciousNameWordsRule(BaseRule):
    def calculate(self, features: FeatureSet) -> int:
        if not self._enabled or features.name.full_name_length == 0:
            return 0
        return self.weight() if features.name.contains_suspicious_words else 0

    def default_description(self) -> str:
        return (
            "Имя содержит подозрительные слова "
            "(crypto, bonus, airdrop, casino, bet, forex, trade)"
        )

    def default_weight(self) -> int:
        return 20


class LongNameRule(BaseRule):
    def calculate(self, features: FeatureSet) -> int:
        if not self._enabled or features.name.full_name_length == 0:
            return 0
        return self.weight() if features.name.full_name_length > 30 else 0

    def default_description(self) -> str:
        return "Имя длиннее 30 символов"

    def default_weight(self) -> int:
        return 10


class TooManyEmojiRule(BaseRule):
    def calculate(self, features: FeatureSet) -> int:
        if not self._enabled or features.name.full_name_length == 0:
            return 0
        return self.weight() if features.name.emoji_count >= TOO_MANY_EMOJI_THRESHOLD else 0

    def default_description(self) -> str:
        return f"Слишком много emoji (>= {TOO_MANY_EMOJI_THRESHOLD})"

    def default_weight(self) -> int:
        return 15


class EmptyNameRule(BaseRule):
    def calculate(self, features: FeatureSet) -> int:
        if not self._enabled:
            return 0
        return self.weight() if features.name.full_name_length == 0 else 0

    def default_description(self) -> str:
        return "Пустое имя"

    def default_weight(self) -> int:
        return 30


class UnknownLanguageRule(BaseRule):
    def calculate(self, features: FeatureSet) -> int:
        if not self._enabled:
            return 0
        return self.weight() if features.profile.language is None else 0

    def default_description(self) -> str:
        return "Язык неизвестен"

    def default_weight(self) -> int:
        return 5


class AccountCreatedTodayRule(BaseRule):
    def calculate(self, features: FeatureSet) -> int:
        if not self._enabled:
            return 0
        return self.weight() if features.profile.account_created_today else 0

    def default_description(self) -> str:
        return "Аккаунт Telegram создан сегодня (оценка по User ID)"

    def default_weight(self) -> int:
        return 35


class NoLinkedPhoneRule(BaseRule):
    def calculate(self, features: FeatureSet) -> int:
        if not self._enabled:
            return 0
        return self.weight() if features.profile.has_linked_phone is False else 0

    def default_description(self) -> str:
        return (
            "К аккаунту не привязан номер телефона "
            "(эвристика: Bot API не передаёт статус напрямую)"
        )

    def default_weight(self) -> int:
        return 15
