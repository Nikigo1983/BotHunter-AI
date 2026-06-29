from abc import ABC, abstractmethod

from app.features.feature_set import FeatureSet

TOO_MANY_EMOJI_THRESHOLD = 3


class BaseRule(ABC):
    @abstractmethod
    def calculate(self, features: FeatureSet) -> int:
        """Return rule score if triggered, otherwise 0."""

    @abstractmethod
    def description(self) -> str:
        """Human-readable rule description."""

    @abstractmethod
    def weight(self) -> int:
        """Maximum score contributed by this rule."""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def is_triggered(self, features: FeatureSet) -> bool:
        return self.calculate(features) > 0
