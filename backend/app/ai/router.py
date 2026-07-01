from app.ai.mock_provider import MockAIProvider
from app.ai.provider import AIProvider
from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AIRouter:
    """Selects AI provider based on configuration."""

    @staticmethod
    def create_primary_provider() -> AIProvider:
        from app.config.runtime_overrides import get_runtime_snapshot

        snapshot = get_runtime_snapshot()
        provider_name = snapshot.ai_provider.strip().lower()
        settings = get_settings()

        if provider_name == "openrouter":
            if settings.openrouter_api_key:
                from app.ai.openrouter_provider import OpenRouterProvider

                return OpenRouterProvider(model=snapshot.openrouter_model)
            logger.warning(
                "OpenRouter selected but OPENROUTER_API_KEY is missing; using MockAIProvider",
            )
            return MockAIProvider()

        if provider_name == "openai":
            if settings.openai_api_key:
                from app.ai.openai_provider import OpenAIProvider

                return OpenAIProvider(model=snapshot.openai_model)
            logger.warning(
                "OpenAI selected but OPENAI_API_KEY is missing; using MockAIProvider",
            )
            return MockAIProvider()

        if provider_name == "mock":
            return MockAIProvider()

        logger.warning("Unknown AI_PROVIDER=%s; using MockAIProvider", provider_name)
        return MockAIProvider()

    @staticmethod
    def create_fallback_provider() -> AIProvider:
        return MockAIProvider()
