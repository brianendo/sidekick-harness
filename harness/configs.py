"""Lead/sidekick pairings to experiment with."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PairConfig:
    name: str
    lead_model: str
    sidekick_model: str | None  # None = the lead works solo
    lead_effort: str = "high"
    sidekick_effort: str = "high"


CONFIGS = {
    c.name: c
    for c in [
        # lead + sidekick pairings
        PairConfig("fable+haiku", "claude-fable-5", "claude-haiku-4-5"),
        PairConfig("fable+sonnet", "claude-fable-5", "claude-sonnet-5"),
        PairConfig("opus+haiku", "claude-opus-4-8", "claude-haiku-4-5"),
        PairConfig("opus+sonnet", "claude-opus-4-8", "claude-sonnet-5"),
        PairConfig("sonnet+haiku", "claude-sonnet-5", "claude-haiku-4-5"),
        # solo baselines
        PairConfig("fable-solo", "claude-fable-5", None),
        PairConfig("opus-solo", "claude-opus-4-8", None),
        PairConfig("sonnet-solo", "claude-sonnet-5", None),
        PairConfig("haiku-solo", "claude-haiku-4-5", None),
    ]
}
