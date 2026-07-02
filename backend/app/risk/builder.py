from app.config.decision_settings import DecisionThresholds, get_decision_thresholds
from app.features.feature_set import FeatureSet
from app.risk.enums import RiskLevel
from app.risk.profile import RiskProfile
from app.rules.base import TOO_MANY_EMOJI_THRESHOLD
from app.rules.engine import RuleEngineResult

SIGNAL_LABELS: dict[str, str] = {
    "no_photo": "отсутствует фотография профиля",
    "no_username": "отсутствует username",
    "random_username": "случайный username",
    "many_digits": "большое количество цифр в username",
    "emoji_name": "много emoji в имени",
    "mixed_alphabet": "смешанный алфавит в имени",
    "unknown_language": "язык неизвестен",
    "premium": "аккаунт Telegram Premium",
    "crypto_keyword": "обнаружены подозрительные ключевые слова",
    "empty_name": "пустое имя",
    "long_name": "слишком длинное имя",
    "account_created_today": "аккаунт создан сегодня",
    "no_linked_phone": "номер телефона не привязан",
}

RULE_MAIN_REASONS: dict[str, str] = {
    "EmptyNameRule": "Пустое имя пользователя",
    "NoPhotoRule": "Отсутствует фотография профиля",
    "UsernameConsecutiveDigitsRule": "Username содержит длинную последовательность цифр",
    "SuspiciousNameWordsRule": "Имя содержит подозрительные слова",
    "UsernameManyDigitsRule": "Username содержит много цифр",
    "TooManyEmojiRule": "В имени слишком много emoji",
    "NoUsernameRule": "Username отсутствует",
    "LongNameRule": "Имя слишком длинное",
    "UnknownLanguageRule": "Язык пользователя неизвестен",
    "AccountCreatedTodayRule": "Аккаунт Telegram создан сегодня",
    "NoLinkedPhoneRule": "К аккаунту не привязан номер телефона",
}


class RiskProfileBuilder:
    def __init__(self, thresholds: DecisionThresholds | None = None) -> None:
        self._thresholds = thresholds or get_decision_thresholds()

    def build(
        self,
        features: FeatureSet,
        rule_result: RuleEngineResult,
        *,
        trust_score: float | None = None,
        rule_score: float | None = None,
        history: list[str] | None = None,
    ) -> RiskProfile:
        signals = self._collect_signals(features)
        risk_level = self._resolve_risk_level(rule_result.rule_score)
        confidence = self._calculate_confidence(rule_result.rule_score, signals)
        main_reason = self._resolve_main_reason(rule_result, signals)
        summary = self._build_summary(signals)

        return RiskProfile(
            risk_level=risk_level,
            confidence=confidence,
            main_reason=main_reason,
            signals=signals,
            summary=summary,
            trust_score=trust_score,
            rule_score=rule_score,
            history=history,
        )

    def _collect_signals(self, features: FeatureSet) -> list[str]:
        signals: list[str] = []

        if not features.profile.has_photo:
            signals.append("no_photo")
        if not features.profile.has_username:
            signals.append("no_username")
        if features.username.contains_random_sequence:
            signals.append("random_username")
        if (
            features.username.digit_count > 6
            or features.username.consecutive_digits > 4
        ):
            signals.append("many_digits")
        if features.name.emoji_count >= TOO_MANY_EMOJI_THRESHOLD:
            signals.append("emoji_name")
        if features.name.mixed_alphabet:
            signals.append("mixed_alphabet")
        if features.profile.language is None:
            signals.append("unknown_language")
        if features.profile.is_premium:
            signals.append("premium")
        if (
            features.username.contains_crypto_words
            or features.name.contains_suspicious_words
        ):
            signals.append("crypto_keyword")
        if features.name.full_name_length == 0:
            signals.append("empty_name")
        if features.name.full_name_length > 30:
            signals.append("long_name")
        if features.profile.account_created_today:
            signals.append("account_created_today")
        if features.profile.has_linked_phone is False:
            signals.append("no_linked_phone")

        return signals

    def _resolve_risk_level(self, rule_score: int) -> RiskLevel:
        if rule_score < self._thresholds.approve_below:
            return RiskLevel.LOW
        if rule_score < self._thresholds.reject_from:
            return RiskLevel.MEDIUM
        return RiskLevel.HIGH

    def _calculate_confidence(self, rule_score: int, signals: list[str]) -> float:
        if rule_score == 0 and not signals:
            return 0.95

        score_factor = min(rule_score / 100.0, 1.0)
        signal_factor = min(len(signals) / 8.0, 1.0)
        confidence = 0.45 + (score_factor * 0.35) + (signal_factor * 0.2)
        return round(min(max(confidence, 0.0), 1.0), 2)

    def _resolve_main_reason(
        self,
        rule_result: RuleEngineResult,
        signals: list[str],
    ) -> str:
        if rule_result.triggered_rules:
            top_rule = max(rule_result.triggered_rules, key=lambda item: item.score)
            return RULE_MAIN_REASONS.get(
                top_rule.rule,
                f"Сработало правило {top_rule.rule}",
            )

        if signals:
            primary_signal = signals[0]
            return SIGNAL_LABELS.get(primary_signal, primary_signal).capitalize()

        return "Явных признаков риска не обнаружено"

    def _build_summary(self, signals: list[str]) -> str:
        if not signals:
            return "Профиль выглядит безопасным: явных признаков риска не обнаружено."

        descriptions = [SIGNAL_LABELS.get(signal, signal) for signal in signals]
        joined = ", ".join(descriptions[:-1])
        if len(descriptions) == 1:
            body = descriptions[0]
        else:
            body = f"{joined} и {descriptions[-1]}"

        return f"Пользователь имеет следующие признаки риска: {body}."
