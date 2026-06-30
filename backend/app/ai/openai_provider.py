import time
from datetime import UTC, datetime

from openai import APIConnectionError, APITimeoutError, OpenAI, OpenAIError, RateLimitError

from app.ai.exceptions import AIProviderError, AITimeoutError
from app.ai.prompt_builder import PromptBuilder
from app.ai.provider import AIProvider
from app.ai.result import AIAnalysisResult
from app.ai.schemas import StructuredAnalysisOutput, structured_output_json_schema
from app.config import get_settings
from app.models.enums import AnalysisDecision
from app.risk.profile import RiskProfile

DECISION_MAP = {
    "Approved": AnalysisDecision.APPROVED,
    "ManualReview": AnalysisDecision.MANUAL_REVIEW,
    "Rejected": AnalysisDecision.REJECTED,
}


class OpenAIProvider(AIProvider):
    """OpenAI provider using structured JSON output."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._model = model or settings.openai_model
        self._timeout = timeout if timeout is not None else settings.openai_timeout
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._client: OpenAI | None = None

        if self._api_key:
            self._client = OpenAI(api_key=self._api_key, timeout=self._timeout)

    @property
    def name(self) -> str:
        return "openai"

    def analyze(self, risk_profile: RiskProfile) -> AIAnalysisResult:
        if not self._client:
            raise AIProviderError("OpenAI API key is not configured")

        prompt = self._prompt_builder.build(risk_profile)
        started = time.perf_counter()

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt.system},
                    {"role": "user", "content": prompt.user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "risk_analysis",
                        "strict": True,
                        "schema": structured_output_json_schema(),
                    },
                },
            )
        except APITimeoutError as exc:
            raise AITimeoutError(str(exc)) from exc
        except (APIConnectionError, RateLimitError, OpenAIError) as exc:
            raise AIProviderError(str(exc)) from exc

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        content = response.choices[0].message.content
        if not content:
            raise AIProviderError("OpenAI returned empty structured response")

        try:
            parsed = StructuredAnalysisOutput.model_validate_json(content)
        except ValueError as exc:
            raise AIProviderError(f"Invalid structured output: {exc}") from exc

        if parsed.decision not in DECISION_MAP:
            raise AIProviderError(f"Unknown decision value: {parsed.decision}")

        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else prompt_tokens + completion_tokens

        return AIAnalysisResult(
            ai_score=parsed.ai_score,
            confidence=round(parsed.confidence, 2),
            decision=DECISION_MAP[parsed.decision],
            reason=parsed.reason,
            provider=self.name,
            response_time_ms=max(elapsed_ms, 1),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            model=self._model,
            created_at=datetime.now(UTC),
        )
