from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.repositories.deps import get_system_setting_repository

SETTING_KEYS = (
    "ai_provider",
    "openrouter_model",
    "openai_model",
    "ai_timeout",
    "ai_max_retries",
    "decision_approve_below",
    "decision_reject_from",
    "monthly_budget_usd",
    "backup_configured",
)


@dataclass(slots=True)
class EffectiveSettings:
    ai_provider: str
    openrouter_model: str
    openai_model: str
    ai_timeout: float
    ai_max_retries: int
    decision_approve_below: int
    decision_reject_from: int
    monthly_budget_usd: float
    backup_configured: bool
    openrouter_base_url: str
    openrouter_api_key: str
    openai_api_key: str
    bot_token: str


class RuntimeSettingsService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._session = session
        self._env = settings or get_settings()
        self._repo = get_system_setting_repository(session)

    async def get_effective_settings(self) -> EffectiveSettings:
        db_values = await self._repo.get_all_settings()
        return EffectiveSettings(
            ai_provider=db_values.get("ai_provider", self._env.ai_provider).strip().lower(),
            openrouter_model=db_values.get("openrouter_model", self._env.openrouter_model),
            openai_model=db_values.get("openai_model", self._env.openai_model),
            ai_timeout=float(db_values.get("ai_timeout", str(self._env.ai_timeout))),
            ai_max_retries=int(db_values.get("ai_max_retries", str(self._env.ai_max_retries))),
            decision_approve_below=int(
                db_values.get("decision_approve_below", str(self._env.decision_approve_below))
            ),
            decision_reject_from=int(
                db_values.get("decision_reject_from", str(self._env.decision_reject_from))
            ),
            monthly_budget_usd=float(
                db_values.get("monthly_budget_usd", str(self._env.monthly_budget_usd))
            ),
            backup_configured=db_values.get("backup_configured", "false").lower() == "true",
            openrouter_base_url=self._env.openrouter_base_url,
            openrouter_api_key=self._env.openrouter_api_key,
            openai_api_key=self._env.openai_api_key,
            bot_token=self._env.bot_token,
        )

    async def update_settings(
        self,
        values: dict[str, str],
        *,
        updated_by: str,
    ) -> EffectiveSettings:
        for key, value in values.items():
            if key in SETTING_KEYS:
                await self._repo.upsert(key, value, updated_by=updated_by)
        effective = await self.get_effective_settings()
        from app.config.runtime_overrides import refresh_runtime_snapshot, snapshot_from_effective, set_runtime_snapshot

        set_runtime_snapshot(snapshot_from_effective(effective))
        return effective

    async def get_db_overrides(self) -> dict[str, str]:
        return await self._repo.get_all_settings()
