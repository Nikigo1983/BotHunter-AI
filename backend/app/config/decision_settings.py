import os
from functools import lru_cache
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, Field, model_validator

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_THRESHOLDS_PATH = BACKEND_DIR / "config" / "decision_thresholds.yaml"


class DecisionThresholds(BaseModel):
    approve_below: int = Field(default=30, ge=0)
    reject_from: int = Field(default=70, ge=0)

    @model_validator(mode="after")
    def validate_thresholds(self) -> Self:
        if self.reject_from <= self.approve_below:
            raise ValueError("reject_from must be greater than approve_below")
        return self


def load_decision_thresholds(path: Path | None = None) -> DecisionThresholds:
    config_path = path or DEFAULT_THRESHOLDS_PATH
    if not config_path.exists():
        return DecisionThresholds()

    with config_path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    thresholds_data = data.get("decision_thresholds", data)
    return DecisionThresholds(**thresholds_data)


@lru_cache
def get_decision_thresholds() -> DecisionThresholds:
    """YAML is the primary source; env vars override when explicitly set."""
    from app.config.settings import get_settings

    thresholds = load_decision_thresholds()
    settings = get_settings()

    if os.getenv("DECISION_APPROVE_BELOW") is not None:
        thresholds = thresholds.model_copy(update={"approve_below": settings.decision_approve_below})
    if os.getenv("DECISION_REJECT_FROM") is not None:
        thresholds = thresholds.model_copy(update={"reject_from": settings.decision_reject_from})

    return thresholds
