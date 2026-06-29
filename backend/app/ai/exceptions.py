class AIError(Exception):
    """Base exception for AI layer."""


class AIProviderError(AIError):
    """Provider failed to return a valid analysis."""


class AITimeoutError(AIError):
    """Provider call exceeded the configured timeout."""
