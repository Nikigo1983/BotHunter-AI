from abc import ABC, abstractmethod

from app.ai.result import AIAnalysisResult
from app.risk.profile import RiskProfile


class AIProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier for logging."""

    @abstractmethod
    def analyze(self, risk_profile: RiskProfile) -> AIAnalysisResult:
        """Analyze risk profile and return structured AI result."""
