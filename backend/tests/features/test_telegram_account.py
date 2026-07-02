from datetime import UTC, datetime

import pytest

from app.config.decision_settings import TelegramAccountHeuristics
from app.features.telegram_account import (
    estimate_telegram_registration_date,
    infer_has_linked_phone,
    is_account_created_on_date,
)

REFERENCE_TIME = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
NEW_ACCOUNT_ID = 9_500_000_000
OLD_ACCOUNT_ID = 10_001
DEFAULT_HEURISTICS = TelegramAccountHeuristics(
    no_phone_inference_max_age_days=45,
    linked_phone_assumed_min_age_days=120,
)

def test_estimate_registration_date_for_old_account() -> None:
    estimated = estimate_telegram_registration_date(
        OLD_ACCOUNT_ID,
        reference_time=REFERENCE_TIME,
    )
    assert estimated.year <= 2014


def test_estimate_registration_date_for_new_account() -> None:
    estimated = estimate_telegram_registration_date(
        NEW_ACCOUNT_ID,
        reference_time=REFERENCE_TIME,
    )
    assert estimated == REFERENCE_TIME.date()


def test_is_account_created_on_date() -> None:
    assert is_account_created_on_date(
        NEW_ACCOUNT_ID,
        reference_time=REFERENCE_TIME,
    ) is True
    assert is_account_created_on_date(
        OLD_ACCOUNT_ID,
        reference_time=REFERENCE_TIME,
    ) is False


def test_infer_has_linked_phone_for_premium() -> None:
    assert (
        infer_has_linked_phone(
            is_premium=True,
            telegram_id=NEW_ACCOUNT_ID,
            reference_time=REFERENCE_TIME,
            heuristics=DEFAULT_HEURISTICS,
        )
        is True
    )


def test_infer_has_linked_phone_for_fresh_non_premium() -> None:
    assert (
        infer_has_linked_phone(
            is_premium=False,
            telegram_id=NEW_ACCOUNT_ID,
            reference_time=REFERENCE_TIME,
            heuristics=DEFAULT_HEURISTICS,
        )
        is False
    )


def test_infer_has_linked_phone_for_old_non_premium() -> None:
    assert (
        infer_has_linked_phone(
            is_premium=False,
            telegram_id=OLD_ACCOUNT_ID,
            reference_time=REFERENCE_TIME,
            heuristics=DEFAULT_HEURISTICS,
        )
        is True
    )


@pytest.mark.parametrize(
    "telegram_id",
    [9_333_000_000],
)
def test_infer_has_linked_phone_unknown_for_middle_age(telegram_id: int) -> None:
    assert (
        infer_has_linked_phone(
            is_premium=False,
            telegram_id=telegram_id,
            reference_time=REFERENCE_TIME,
            heuristics=DEFAULT_HEURISTICS,
        )
        is None
    )
