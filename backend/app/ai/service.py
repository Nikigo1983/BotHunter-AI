from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from app.ai.cost import estimate_request_cost_usd
from app.ai.enums import AIServiceStatus
from app.ai.exceptions import AIError, AIProviderError, AITimeoutError
from app.ai.provider import AIProvider
from app.ai.result import AIServiceResult
from app.ai.router import AIRouter
from app.config import get_settings
from app.models.enums import AnalysisDecision
from app.risk.profile import RiskProfile
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AIService:
    """Calls AI only for MANUAL_REVIEW decisions."""

    def __init__(
        self,
        provider: AIProvider | None = None,
        fallback_provider: AIProvider | None = None,
        max_retries: int | None = None,
        timeout: float | None = None,
    ) -> None:
        settings = get_settings()
        self._provider = provider
        self._fallback_provider = fallback_provider
        self._max_retries = max_retries if max_retries is not None else settings.ai_max_retries
        self._timeout = timeout if timeout is not None else settings.ai_timeout

    @staticmethod
    def _create_default_provider() -> AIProvider:
        return AIRouter.create_primary_provider()

    def _get_provider(self) -> AIProvider:
        if self._provider is None:
            self._provider = self._create_default_provider()
        return self._provider

    def _get_fallback_provider(self) -> AIProvider:
        if self._fallback_provider is None:
            self._fallback_provider = AIRouter.create_fallback_provider()
        return self._fallback_provider

    def analyze(
        self,
        decision: AnalysisDecision,
        risk_profile: RiskProfile,
    ) -> AIServiceResult:
        if decision != AnalysisDecision.MANUAL_REVIEW:
            logger.debug(
                "AI skipped for decision=%s risk_level=%s",
                decision.value,
                risk_profile.risk_level.value,
            )
            return AIServiceResult(status=AIServiceStatus.SKIPPED)

        last_error: AIError | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                result = self._call_with_timeout(self._get_provider(), risk_profile)
                service_result = AIServiceResult(status=AIServiceStatus.SUCCESS, analysis=result)
                self._log_success(result, attempt=attempt, used_fallback=False)
                return service_result
            except AIError as exc:
                last_error = exc
                logger.warning(
                    "AI provider attempt failed provider=%s attempt=%s/%s error=%s",
                    self._get_provider().name,
                    attempt,
                    self._max_retries,
                    exc,
                )

        try:
            fallback_result = self._call_with_timeout(
                self._get_fallback_provider(),
                risk_profile,
            )
            service_result = AIServiceResult(
                status=AIServiceStatus.FALLBACK,
                analysis=fallback_result,
            )
            self._log_success(fallback_result, attempt=0, used_fallback=True)
            logger.warning(
                "Primary AI unavailable, fallback provider used primary=%s fallback=%s error=%s",
                self._get_provider().name,
                self._get_fallback_provider().name,
                last_error,
            )
            return service_result
        except AIError as fallback_error:
            logger.error(
                "AI unavailable primary=%s fallback=%s primary_error=%s fallback_error=%s",
                self._get_provider().name,
                self._get_fallback_provider().name,
                last_error,
                fallback_error,
            )
            return AIServiceResult(
                status=AIServiceStatus.UNAVAILABLE,
                error_message=str(fallback_error),
            )

    def _call_with_timeout(
        self,
        provider: AIProvider,
        risk_profile: RiskProfile,
    ):
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(provider.analyze, risk_profile)
            try:
                return future.result(timeout=self._timeout)
            except FuturesTimeoutError as exc:
                raise AITimeoutError(
                    f"{provider.name} timed out after {self._timeout}s",
                ) from exc
            except AIError:
                raise
            except Exception as exc:
                raise AIProviderError(
                    f"{provider.name} failed: {exc}",
                ) from exc

    def _log_success(
        self,
        result,
        *,
        attempt: int,
        used_fallback: bool,
    ) -> None:
        cost = estimate_request_cost_usd(
            result.model,
            result.prompt_tokens,
            result.completion_tokens,
        )
        logger.info(
            (
                "AI analysis completed provider=%s model=%s fallback=%s attempt=%s "
                "response_time_ms=%s prompt_tokens=%s completion_tokens=%s "
                "total_tokens=%s estimated_cost_usd=%s decision=%s ai_score=%s"
            ),
            result.provider,
            result.model,
            used_fallback,
            attempt,
            result.response_time_ms,
            result.prompt_tokens,
            result.completion_tokens,
            result.total_tokens,
            cost,
            result.decision.value,
            result.ai_score,
        )
