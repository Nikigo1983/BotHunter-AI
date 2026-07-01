from abc import ABC, abstractmethod

from app.features.feature_set import FeatureSet

TOO_MANY_EMOJI_THRESHOLD = 3


class BaseRule(ABC):
    def __init__(
        self,
        *,
        score: int | None = None,
        enabled: bool = True,
        description_override: str | None = None,
    ) -> None:
        self._score = score
        self._enabled = enabled
        self._description_override = description_override

    @abstractmethod
    def calculate(self, features: FeatureSet) -> int:
        """Return rule score if triggered, otherwise 0."""

    def description(self) -> str:
        return self._description_override or self.default_description()

    @abstractmethod
    def default_description(self) -> str:
        """Human-readable rule description."""

    def weight(self) -> int:
        return self._score if self._score is not None else self.default_weight()

    @abstractmethod
    def default_weight(self) -> int:
        """Default score contributed by this rule."""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def is_enabled(self) -> bool:
        return self._enabled

    def is_triggered(self, features: FeatureSet) -> bool:
        if not self._enabled:
            return False
        return self.calculate(features) > 0
