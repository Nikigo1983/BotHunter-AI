from dataclasses import asdict, dataclass
from typing import Any

from app.risk.enums import RiskLevel


@dataclass(slots=True)
class RiskProfile:
    risk_level: RiskLevel
    confidence: float
    main_reason: str
    signals: list[str]
    summary: str
    trust_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["risk_level"] = self.risk_level.value
        return data
