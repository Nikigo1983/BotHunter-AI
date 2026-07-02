from pathlib import Path

import pytest

from app.config.decision_settings import (
    TelegramAccountHeuristics,
    load_decision_thresholds,
    load_telegram_account_heuristics,
)


def test_load_decision_thresholds_from_default_yaml() -> None:
    thresholds = load_decision_thresholds()
    assert thresholds.approve_below == 30
    assert thresholds.reject_from == 70


def test_load_telegram_account_heuristics_from_default_yaml() -> None:
    heuristics = load_telegram_account_heuristics()
    assert heuristics.no_phone_inference_max_age_days == 45
    assert heuristics.linked_phone_assumed_min_age_days == 120


def test_load_telegram_account_heuristics_from_custom_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "decision_thresholds.yaml"
    config_path.write_text(
        """
decision_thresholds:
  approve_below: 25
  reject_from: 80

telegram_account_heuristics:
  no_phone_inference_max_age_days: 14
  linked_phone_assumed_min_age_days: 90
""".strip(),
        encoding="utf-8",
    )

    heuristics = load_telegram_account_heuristics(config_path)
    thresholds = load_decision_thresholds(config_path)

    assert thresholds.approve_below == 25
    assert thresholds.reject_from == 80
    assert heuristics.no_phone_inference_max_age_days == 14
    assert heuristics.linked_phone_assumed_min_age_days == 90


def test_telegram_account_heuristics_validate_age_windows() -> None:
    with pytest.raises(ValueError, match="linked_phone_assumed_min_age_days"):
        TelegramAccountHeuristics(
            no_phone_inference_max_age_days=120,
            linked_phone_assumed_min_age_days=45,
        )
