MODEL_PRICING_PER_MILLION: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "claude-sonnet-4": (3.00, 15.00),
    "gemini-2.5-pro": (1.25, 10.00),
    "deepseek-chat": (0.14, 0.28),
    "llama-3.3-70b-instruct": (0.40, 0.40),
}

DEFAULT_PRICING = (0.15, 0.60)


def _normalize_model_name(model: str) -> str:
    if "/" in model:
        return model.split("/", 1)[1]
    return model


def estimate_request_cost_usd(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    normalized = _normalize_model_name(model)
    input_rate, output_rate = MODEL_PRICING_PER_MILLION.get(normalized, DEFAULT_PRICING)
    input_cost = (prompt_tokens / 1_000_000) * input_rate
    output_cost = (completion_tokens / 1_000_000) * output_rate
    return round(input_cost + output_cost, 6)
