"""Per-model pricing and cost computation from API usage objects."""

# $ per million tokens (sticker prices, 2026-07)
PRICING = {
    "claude-fable-5": {"input": 10.00, "output": 50.00},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

CACHE_WRITE_MULT = 1.25  # 5-minute TTL cache write premium
CACHE_READ_MULT = 0.10


def resolve_pricing(model: str) -> dict:
    """Match a served model id (may carry a suffix) to a pricing entry."""
    if model in PRICING:
        return PRICING[model]
    for known, price in PRICING.items():
        if model.startswith(known):
            return price
    raise KeyError(f"No pricing entry for model {model!r} — add it to PRICING")


def usage_cost_usd(model: str, usage) -> float:
    """Cost of one API response, including prompt-cache reads/writes."""
    p = resolve_pricing(model)
    inp = usage.input_tokens or 0
    out = usage.output_tokens or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    return (
        inp * p["input"]
        + cache_write * p["input"] * CACHE_WRITE_MULT
        + cache_read * p["input"] * CACHE_READ_MULT
        + out * p["output"]
    ) / 1_000_000
