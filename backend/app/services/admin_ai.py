from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.repositories.deps import get_ai_usage_repository


@dataclass(slots=True)
class AIUsageStatisticsDTO:
    total_requests: int
    total_tokens: int
    total_cost: float
    avg_latency_ms: float
    top_models: list[dict]
    daily_stats: list[dict]


@dataclass(slots=True)
class AISettingsDTO:
    provider: str
    model: str
    timeout: float
    max_retries: int
    fallback: str
    openrouter_base_url: str
    api_key_configured: bool


class AdminAIService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._usage_repo = get_ai_usage_repository(session)

    async def get_usage_statistics(self) -> AIUsageStatisticsDTO:
        raw = await self._usage_repo.get_statistics()
        return AIUsageStatisticsDTO(
            total_requests=int(raw["total_requests"]),
            total_tokens=int(raw["total_tokens"]),
            total_cost=float(raw["total_cost"]),
            avg_latency_ms=float(raw["avg_latency_ms"]),
            top_models=list(raw["top_models"]),
            daily_stats=list(raw["daily_stats"]),
        )

    def get_ai_settings(self) -> AISettingsDTO:
        settings = get_settings()
        provider = settings.ai_provider.strip().lower()
        if provider == "openrouter":
            model = settings.openrouter_model
            api_key_configured = bool(settings.openrouter_api_key)
        elif provider == "openai":
            model = settings.openai_model
            api_key_configured = bool(settings.openai_api_key)
        else:
            model = "mock-v1"
            api_key_configured = True

        return AISettingsDTO(
            provider=provider,
            model=model,
            timeout=settings.ai_timeout,
            max_retries=settings.ai_max_retries,
            fallback="mock",
            openrouter_base_url=settings.openrouter_base_url,
            api_key_configured=api_key_configured,
        )
