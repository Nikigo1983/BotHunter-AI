import json
import re
import time
from datetime import UTC, datetime

import httpx

from app.ai.exceptions import AIProviderError, AITimeoutError
from app.ai.prompt_builder import Prompt, PromptBuilder
from app.ai.provider import AIProvider
from app.ai.result import AIAnalysisResult
from app.ai.schemas import StructuredAnalysisOutput
from app.config import get_settings
from app.models.enums import AnalysisDecision
from app.risk.profile import RiskProfile
from app.utils.logging import get_logger

logger = get_logger(__name__)

DECISION_MAP = {
    "Approved": AnalysisDecision.APPROVED,
    "ManualReview": AnalysisDecision.MANUAL_REVIEW,
    "Rejected": AnalysisDecision.REJECTED,
}

JSON_OUTPUT_INSTRUCTION = (
    "Return only one valid JSON object. Do not use markdown, code fences, "
    "or any text outside JSON. Required fields: "
    "risk_score (integer 0-100), confidence (float 0-1), "
    "decision (Approved|ManualReview|Rejected), reason (string), "
    "recommended_action (Approve|ManualReview|Reject), signals (array of strings)."
)


class OpenRouterProvider(AIProvider):
    """Universal LLM provider via OpenRouter HTTP API (no OpenAI SDK)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.openrouter_api_key
        self._model = model or settings.openrouter_model
        self._base_url = (base_url or settings.openrouter_base_url).rstrip("/")
        self._timeout = timeout if timeout is not None else settings.ai_timeout
        self._prompt_builder = prompt_builder or PromptBuilder()

    @property
    def name(self) -> str:
        return "openrouter"

    def analyze(self, risk_profile: RiskProfile) -> AIAnalysisResult:
        if not self._api_key:
            raise AIProviderError("OpenRouter API key is not configured")

        prompt = self._prompt_builder.build(risk_profile)
        payload = {
            "model": self._model,
            "messages": self._build_messages(prompt),
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://bothunter.ai",
            "X-Title": "BotHunter AI",
        }

        started = time.perf_counter()
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise AITimeoutError(
                f"OpenRouter timed out after {self._timeout}s",
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._raise_http_error(exc)
        except httpx.HTTPError as exc:
            raise AIProviderError(f"OpenRouter request failed: {exc}") from exc

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        if not content:
            raise AIProviderError("OpenRouter returned empty structured response")

        parsed = self._parse_structured_output(content)

        if parsed.decision not in DECISION_MAP:
            raise AIProviderError(f"Unknown decision value: {parsed.decision}")

        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or prompt_tokens + completion_tokens)

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

    @staticmethod
    def _build_messages(prompt: Prompt) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": f"{prompt.system} {JSON_OUTPUT_INSTRUCTION}",
            },
            {"role": "user", "content": prompt.user},
        ]

    @staticmethod
    def _parse_structured_output(content: str) -> StructuredAnalysisOutput:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            return StructuredAnalysisOutput.model_validate_json(cleaned)
        except ValueError as exc:
            logger.error("OpenRouter invalid JSON response: %s", exc)
            raise AIProviderError(f"Invalid structured output: {exc}") from exc

    def _raise_http_error(self, exc: httpx.HTTPStatusError) -> None:
        status = exc.response.status_code
        detail = self._safe_error_detail(exc.response)
        logger.error("OpenRouter HTTP error status=%s detail=%s", status, detail)
        raise AIProviderError(f"OpenRouter HTTP error: {status}") from exc

    def _safe_error_detail(self, response: httpx.Response) -> str:
        detail = ""
        try:
            body = response.json()
            error = body.get("error", body)
            if isinstance(error, dict):
                detail = str(error.get("message", error))
            else:
                detail = str(error)
        except (json.JSONDecodeError, ValueError):
            detail = response.text[:200]

        if self._api_key:
            detail = detail.replace(self._api_key, "***")
        return detail
