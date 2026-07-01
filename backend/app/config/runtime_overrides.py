from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, get_settings

_cache: EffectiveSettingsSnapshot | None = None


@dataclass(slots=True)
class EffectiveSettingsSnapshot:
    ai_provider: str
    openrouter_model: str
    openai_model: str
    ai_timeout: float
    ai_max_retries: int
    decision_approve_below: int
    decision_reject_from: int
    monthly_budget_usd: float


def set_runtime_snapshot(snapshot: EffectiveSettingsSnapshot | None) -> None:
    global _cache
    _cache = snapshot


def clear_runtime_snapshot() -> None:
    set_runtime_snapshot(None)


def get_runtime_snapshot() -> EffectiveSettingsSnapshot:
    global _cache
    if _cache is not None:
        return _cache
    settings = get_settings()
    snapshot = EffectiveSettingsSnapshot(
        ai_provider=settings.ai_provider.strip().lower(),
        openrouter_model=settings.openrouter_model,
        openai_model=settings.openai_model,
        ai_timeout=settings.ai_timeout,
        ai_max_retries=settings.ai_max_retries,
        decision_approve_below=settings.decision_approve_below,
        decision_reject_from=settings.decision_reject_from,
        monthly_budget_usd=settings.monthly_budget_usd,
    )
    _cache = snapshot
    return snapshot


def snapshot_from_effective(effective) -> EffectiveSettingsSnapshot:
    return EffectiveSettingsSnapshot(
        ai_provider=effective.ai_provider,
        openrouter_model=effective.openrouter_model,
        openai_model=effective.openai_model,
        ai_timeout=effective.ai_timeout,
        ai_max_retries=effective.ai_max_retries,
        decision_approve_below=effective.decision_approve_below,
        decision_reject_from=effective.decision_reject_from,
        monthly_budget_usd=effective.monthly_budget_usd,
    )


async def refresh_runtime_snapshot(session) -> EffectiveSettingsSnapshot:
    from app.services.runtime_settings import RuntimeSettingsService

    effective = await RuntimeSettingsService(session).get_effective_settings()
    snapshot = snapshot_from_effective(effective)
    set_runtime_snapshot(snapshot)
    return snapshot
