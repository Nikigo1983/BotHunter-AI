from app.ai.cost import estimate_request_cost_usd
from app.ai.enums import AIServiceStatus
from app.ai.exceptions import AIError, AIProviderError, AITimeoutError
from app.ai.mock_provider import MockAIProvider
from app.ai.prompt_builder import Prompt, PromptBuilder
from app.ai.provider import AIProvider
from app.ai.result import AIAnalysisResult, AIServiceResult
from app.ai.schemas import StructuredAnalysisOutput
from app.ai.service import AIService

__all__ = [
    "AIAnalysisResult",
    "AIError",
    "AIProvider",
    "AIProviderError",
    "AIService",
    "AIServiceResult",
    "AIServiceStatus",
    "AITimeoutError",
    "AIRouter",
    "MockAIProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
    "Prompt",
    "PromptBuilder",
    "StructuredAnalysisOutput",
    "estimate_request_cost_usd",
]


def __getattr__(name: str):
    if name == "OpenAIProvider":
        from app.ai.openai_provider import OpenAIProvider

        return OpenAIProvider
    if name == "OpenRouterProvider":
        from app.ai.openrouter_provider import OpenRouterProvider

        return OpenRouterProvider
    if name == "AIRouter":
        from app.ai.router import AIRouter

        return AIRouter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
