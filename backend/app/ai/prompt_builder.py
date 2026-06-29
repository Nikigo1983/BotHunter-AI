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
        "Do not infer or request personal identifiers."
    )

    def build(self, risk_profile: RiskProfile) -> Prompt:
        signals = ", ".join(risk_profile.signals) if risk_profile.signals else "none"
        user_message = (
            "Risk profile (no personal data):\n"
            f"- Risk level: {risk_profile.risk_level.value}\n"
            f"- Confidence: {risk_profile.confidence:.2f}\n"
            f"- Signals: {signals}\n"
            f"- Summary: {risk_profile.summary}"
        )
        return Prompt(system=self.SYSTEM_MESSAGE, user=user_message)
