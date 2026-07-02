from __future__ import annotations

from datetime import UTC, date, datetime

from app.config.decision_settings import TelegramAccountHeuristics, get_telegram_account_heuristics

# Reference points for linear interpolation (User ID -> registration date).# Telegram does not expose registration timestamps; estimates are approximate.
TELEGRAM_ID_REFERENCE_POINTS: tuple[tuple[int, date], ...] = (
    (1_000_000, date(2013, 8, 14)),
    (10_000_000, date(2014, 2, 15)),
    (50_000_000, date(2014, 10, 1)),
    (100_000_000, date(2015, 6, 4)),
    (250_000_000, date(2016, 3, 1)),
    (500_000_000, date(2017, 1, 1)),
    (750_000_000, date(2017, 9, 1)),
    (1_000_000_000, date(2018, 5, 1)),
    (1_500_000_000, date(2019, 2, 1)),
    (2_000_000_000, date(2019, 10, 1)),
    (3_000_000_000, date(2020, 8, 1)),
    (4_000_000_000, date(2021, 5, 1)),
    (5_000_000_000, date(2022, 2, 1)),
    (6_000_000_000, date(2023, 1, 1)),
    (7_000_000_000, date(2024, 1, 1)),
    (7_500_000_000, date(2024, 7, 1)),
    (8_000_000_000, date(2025, 1, 1)),
    (8_500_000_000, date(2025, 7, 1)),
    (9_000_000_000, date(2026, 1, 1)),
    (9_500_000_000, date(2026, 6, 30)),
)


def estimate_telegram_registration_date(    telegram_id: int,
    *,
    reference_time: datetime | None = None,
) -> date:
    now = reference_time or datetime.now(UTC)
    points = TELEGRAM_ID_REFERENCE_POINTS

    if telegram_id <= points[0][0]:
        return points[0][1]

    for index in range(len(points) - 1):
        left_id, left_date = points[index]
        right_id, right_date = points[index + 1]
        if left_id <= telegram_id <= right_id:
            return _interpolate_date(telegram_id, left_id, left_date, right_id, right_date)

    last_id, last_date = points[-2]
    extrapolated_id, extrapolated_date = points[-1]
    estimated = _interpolate_date(
        telegram_id,
        last_id,
        last_date,
        extrapolated_id,
        extrapolated_date,
    )
    return min(estimated, now.date())


def is_account_created_on_date(
    telegram_id: int,
    *,
    reference_time: datetime | None = None,
) -> bool:
    now = reference_time or datetime.now(UTC)
    estimated = estimate_telegram_registration_date(
        telegram_id,
        reference_time=now,
    )
    return estimated == now.date()


def infer_has_linked_phone(
    *,
    is_premium: bool,
    telegram_id: int,
    reference_time: datetime | None = None,
    heuristics: TelegramAccountHeuristics | None = None,
) -> bool | None:
    """Best-effort phone linkage signal.

    Telegram Bot API does not expose whether a phone number is linked.
    Premium accounts and long-lived accounts are treated as verified; fresh
    non-premium accounts are treated as likely unverified.
    """
    if is_premium:
        return True

    cfg = heuristics or get_telegram_account_heuristics()
    now = reference_time or datetime.now(UTC)
    estimated = estimate_telegram_registration_date(
        telegram_id,
        reference_time=now,
    )
    age_days = max(0, (now.date() - estimated).days)

    if age_days > cfg.linked_phone_assumed_min_age_days:
        return True
    if age_days <= cfg.no_phone_inference_max_age_days:
        return False
    return None

def _interpolate_date(
    telegram_id: int,
    left_id: int,
    left_date: date,
    right_id: int,
    right_date: date,
) -> date:
    if left_id == right_id:
        return left_date

    left_ts = datetime.combine(left_date, datetime.min.time(), tzinfo=UTC).timestamp()
    right_ts = datetime.combine(right_date, datetime.min.time(), tzinfo=UTC).timestamp()
    ratio = (telegram_id - left_id) / (right_id - left_id)
    estimated_ts = left_ts + (right_ts - left_ts) * ratio
    return datetime.fromtimestamp(estimated_ts, tz=UTC).date()
