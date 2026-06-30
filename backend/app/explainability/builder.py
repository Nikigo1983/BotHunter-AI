import re
from dataclasses import dataclass
from typing import Any

RULE_NEGATIVE_LABELS: dict[str, str] = {
    "NoPhotoRule": "Нет фотографии профиля",
    "NoUsernameRule": "Username отсутствует",
    "UsernameManyDigitsRule": "Username содержит более 6 цифр",
    "UsernameConsecutiveDigitsRule": "Username содержит подряд более 4 цифр",
    "SuspiciousNameWordsRule": (
        "Имя содержит подозрительные слова (crypto, bonus, airdrop и др.)"
    ),
    "LongNameRule": "Имя длиннее 30 символов",
    "TooManyEmojiRule": "Слишком много emoji в имени",
    "EmptyNameRule": "Пустое имя",
    "UnknownLanguageRule": "Язык профиля неизвестен",
}

TRUST_POSITIVE_THRESHOLD = 70.0
TRUST_NEGATIVE_THRESHOLD = 40.0
USERNAME_DIGIT_SOFT_THRESHOLD = 6


@dataclass(slots=True)
class HybridSignals:
    positive_signals: list[str]
    negative_signals: list[str]


class HybridExplainabilityBuilder:
    """Merge deterministic profile/rule/reputation signals with AI explanations."""

    @classmethod
    def build(
        cls,
        *,
        feature_set: dict[str, Any],
        trust_score: float,
        triggered_rules: list[dict[str, Any]] | None = None,
        rule_score: float | None = None,
        ai_positive: list[str] | None = None,
        ai_negative: list[str] | None = None,
    ) -> HybridSignals:
        system_positive = cls._system_positive_signals(feature_set, trust_score, rule_score)
        system_negative = cls._system_negative_signals(
            feature_set,
            triggered_rules or [],
            trust_score,
        )

        positive = cls._merge_unique(system_positive, ai_positive or [])
        ai_negative_filtered = cls._filter_conflicting_ai_negatives(positive, ai_negative or [])
        ai_negative_filtered = cls._filter_redundant_ai_negatives(system_negative, ai_negative_filtered)
        negative = cls._merge_unique(system_negative, ai_negative_filtered)

        return HybridSignals(positive_signals=positive, negative_signals=negative)

    @staticmethod
    def risk_level(score: float | None) -> str | None:
        if score is None:
            return None
        if score < 30:
            return "low"
        if score < 70:
            return "medium"
        return "high"

    @staticmethod
    def risk_level_label(score: float | None) -> str | None:
        mapping = {
            "low": "Низкий риск",
            "medium": "Средний риск",
            "high": "Высокий риск",
        }
        level = HybridExplainabilityBuilder.risk_level(score)
        return mapping.get(level) if level else None

    @classmethod
    def _system_positive_signals(
        cls,
        feature_set: dict[str, Any],
        trust_score: float,
        rule_score: float | None,
    ) -> list[str]:
        profile = feature_set.get("profile") or {}
        username = feature_set.get("username") or {}
        signals: list[str] = []

        if profile.get("has_photo"):
            signals.append("Есть фотография профиля")
        if profile.get("has_username"):
            signals.append("Есть читаемый username")
        if profile.get("is_premium"):
            signals.append("Premium-аккаунт")
        if username.get("contains_dictionary_words"):
            signals.append("Username содержит осмысленные слова")
        if trust_score >= TRUST_POSITIVE_THRESHOLD:
            signals.append(f"Репутация {int(round(trust_score))}/100")
        if rule_score is not None and rule_score == 0:
            signals.append("Rule Engine: правила не сработали")

        return signals

    @classmethod
    def _system_negative_signals(
        cls,
        feature_set: dict[str, Any],
        triggered_rules: list[dict[str, Any]],
        trust_score: float,
    ) -> list[str]:
        profile = feature_set.get("profile") or {}
        username = feature_set.get("username") or {}
        name = feature_set.get("name") or {}
        signals: list[str] = []

        for rule in triggered_rules:
            rule_name = str(rule.get("rule", ""))
            label = RULE_NEGATIVE_LABELS.get(rule_name)
            if label:
                signals.append(label)

        if profile.get("has_username") and 0 < int(username.get("digit_count", 0)) <= USERNAME_DIGIT_SOFT_THRESHOLD:
            if not any("цифр" in item for item in signals):
                signals.append("Username содержит цифры")

        if username.get("contains_crypto_words"):
            signals.append("Username содержит крипто-признаки")
        if username.get("contains_random_sequence"):
            signals.append("Username выглядит случайным")
        if name.get("contains_suspicious_words") and not any("подозритель" in item for item in signals):
            signals.append("Имя содержит подозрительные слова")
        if name.get("mixed_alphabet"):
            signals.append("Имя содержит смешанные алфавиты")
        if int(name.get("emoji_count", 0)) > 0 and not any("emoji" in item.lower() for item in signals):
            signals.append("Имя содержит emoji")

        trust_negative = cls._system_trust_negative(trust_score)
        if trust_negative:
            signals.append(trust_negative)

        return signals

    @classmethod
    def _system_trust_negative(cls, trust_score: float) -> str | None:
        if trust_score <= TRUST_NEGATIVE_THRESHOLD:
            return f"Низкая репутация ({int(round(trust_score))}/100)"
        return None

    @classmethod
    def _merge_unique(cls, primary: list[str], secondary: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for item in [*primary, *secondary]:
            cleaned = item.strip()
            if not cleaned:
                continue
            key = cls._normalize(cleaned)
            if key in seen:
                continue
            seen.add(key)
            merged.append(cleaned)
        return merged

    @staticmethod
    def _normalize(text: str) -> str:
        collapsed = re.sub(r"\s+", " ", text.lower().strip())
        return re.sub(r"[^\w\s/]", "", collapsed, flags=re.UNICODE)

    @classmethod
    def _filter_conflicting_ai_negatives(
        cls,
        positives: list[str],
        ai_negatives: list[str],
    ) -> list[str]:
        if not ai_negatives:
            return []

        positive_blob = " ".join(positives).lower()
        has_photo = "есть фото" in positive_blob or "фотограф" in positive_blob
        has_username = "есть читаемый username" in positive_blob or (
            "username" in positive_blob and "есть" in positive_blob
        )

        filtered: list[str] = []
        for item in ai_negatives:
            lowered = item.lower()
            if has_photo and "фото" in lowered and ("нет" in lowered or "отсутств" in lowered):
                continue
            if has_username and "username" in lowered and ("нет" in lowered or "отсутств" in lowered):
                continue
            filtered.append(item)
        return filtered

    @classmethod
    def _filter_redundant_ai_negatives(
        cls,
        system_negatives: list[str],
        ai_negatives: list[str],
    ) -> list[str]:
        if not ai_negatives:
            return []

        system_blob = " ".join(system_negatives).lower()
        filtered: list[str] = []
        for item in ai_negatives:
            lowered = item.lower()
            if "фото" in lowered and "фото" in system_blob:
                continue
            if "username" in lowered and "username" in system_blob:
                continue
            filtered.append(item)
        return filtered
