"""Single entry point for model calls. Handles the per-model API quirks:

- claude-fable-5: thinking is always on (omit the param); server-side refusal
  fallback to Opus 4.8 enabled by default (beta `server-side-fallback-2026-06-01`).
- claude-opus-4-8: adaptive thinking must be set explicitly.
- claude-sonnet-5: adaptive thinking is the default; set explicitly for clarity.
- claude-haiku-4-5: no adaptive thinking, no effort parameter.

All calls stream (large max_tokens would otherwise hit HTTP timeouts) and
return the accumulated final message.
"""

import anthropic

MAX_TOKENS = 32_000

_EFFORT_MODELS = ("claude-fable-5", "claude-opus-4-8", "claude-sonnet-5")
_ADAPTIVE_MODELS = ("claude-opus-4-8", "claude-sonnet-5")


def make_client() -> anthropic.Anthropic:
    # Zero-arg client: resolves ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN /
    # `ant auth login` profile from the environment.
    return anthropic.Anthropic()


def call_model(
    client: anthropic.Anthropic,
    *,
    model: str,
    system: str,
    tools: list[dict],
    messages: list,
    effort: str = "high",
    fable_fallback: bool = True,
):
    kwargs: dict = dict(
        model=model,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        tools=tools,
        messages=messages,
    )
    if model in _ADAPTIVE_MODELS:
        kwargs["thinking"] = {"type": "adaptive"}
    if model in _EFFORT_MODELS:
        kwargs["output_config"] = {"effort": effort}
    if model == "claude-fable-5" and fable_fallback:
        kwargs["betas"] = ["server-side-fallback-2026-06-01"]
        kwargs["fallbacks"] = [{"model": "claude-opus-4-8"}]

    with client.beta.messages.stream(**kwargs) as stream:
        return stream.get_final_message()


def served_by_fallback(response) -> bool:
    """True if a fallback model produced this response (Fable refusal path)."""
    iterations = getattr(response.usage, "iterations", None) or []
    return any(getattr(it, "type", None) == "fallback_message" for it in iterations)
