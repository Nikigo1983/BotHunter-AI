import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Self

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


class TelegramAccountHeuristics(BaseModel):
    no_phone_inference_max_age_days: int = Field(default=45, ge=0)
    linked_phone_assumed_min_age_days: int = Field(default=120, ge=1)

    @model_validator(mode="after")
    def validate_age_windows(self) -> Self:
        if self.linked_phone_assumed_min_age_days <= self.no_phone_inference_max_age_days:
            raise ValueError(
                "linked_phone_assumed_min_age_days must be greater than "
                "no_phone_inference_max_age_days"
            )
        return self


def _load_config_data(path: Path | None = None) -> dict[str, Any]:
    config_path = path or DEFAULT_THRESHOLDS_PATH
    if not config_path.exists():
        return {}

    with config_path.open(encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_decision_thresholds(path: Path | None = None) -> DecisionThresholds:
    data = _load_config_data(path)
    thresholds_data = data.get("decision_thresholds", data)
    return DecisionThresholds(**thresholds_data)


def load_telegram_account_heuristics(path: Path | None = None) -> TelegramAccountHeuristics:
    data = _load_config_data(path)
    heuristics_data = data.get("telegram_account_heuristics", {})
    return TelegramAccountHeuristics(**heuristics_data)


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


@lru_cache
def get_telegram_account_heuristics() -> TelegramAccountHeuristics:
    """YAML is the primary source; env vars override when explicitly set."""
    from app.config.settings import get_settings

    heuristics = load_telegram_account_heuristics()
    settings = get_settings()

    if os.getenv("TELEGRAM_NO_PHONE_MAX_AGE_DAYS") is not None:
        heuristics = heuristics.model_copy(
            update={"no_phone_inference_max_age_days": settings.telegram_no_phone_max_age_days}
        )
    if os.getenv("TELEGRAM_LINKED_PHONE_MIN_AGE_DAYS") is not None:
        heuristics = heuristics.model_copy(
            update={
                "linked_phone_assumed_min_age_days": settings.telegram_linked_phone_min_age_days
            }
        )

    return heuristics
