from dataclasses import dataclass

from app.risk.profile import RiskProfile


@dataclass(frozen=True, slots=True)
class Prompt:
    system: str
    user: str


class PromptBuilder:
    SYSTEM_MESSAGE = (
        "You are a Telegram channel join-request risk analyst. "
        "Analyze the anonymized risk profile and respond strictly in JSON "
        "according to the provided schema. "
        "Provide an explainable assessment: clear reason, recommended_action, "
        "positive_signals, negative_signals, and short_summary. "
        "Do not infer or request personal identifiers."
    )

    def build(self, risk_profile: RiskProfile) -> Prompt:
        signals = ", ".join(risk_profile.signals) if risk_profile.signals else "none"
        history_lines = (
            "\n".join(f"- {item}" for item in risk_profile.history)
            if risk_profile.history
            else "none"
        )
        trust_score = (
            f"{risk_profile.trust_score:.0f}"
            if risk_profile.trust_score is not None
            else "unknown"
        )
        rule_score = (
            f"{risk_profile.rule_score:.0f}"
            if risk_profile.rule_score is not None
            else "unknown"
        )
        user_message = (
            "Risk profile (no personal data):\n"
            f"- Risk level: {risk_profile.risk_level.value}\n"
            f"- Rule score: {rule_score}\n"
            f"- Trust score: {trust_score}\n"
            f"- Confidence: {risk_profile.confidence:.2f}\n"
            f"- Signals: {signals}\n"
            f"- Summary: {risk_profile.summary}\n"
            f"- History:\n{history_lines}"
        )
        return Prompt(system=self.SYSTEM_MESSAGE, user=user_message)
