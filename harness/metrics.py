"""Run-level accounting: tokens, cost, turns, and the behavioral metrics
from Cognition's Fable-vs-Opus writeup (lead edits, delegation timing)."""

from dataclasses import dataclass, field

from .pricing import usage_cost_usd


@dataclass
class ModelSpend:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class Ledger:
    """Accumulates spend per (role, served-model) plus behavioral counters."""

    spend: dict = field(default_factory=dict)  # (role, model) -> ModelSpend
    lead_turns: int = 0
    sidekick_turns: int = 0
    lead_code_edits: int = 0        # write_file/edit_file calls made by the lead
    delegations: int = 0
    first_delegation_turn: int | None = None  # lead turn number of first delegate call
    refusals: int = 0
    fallbacks_served: int = 0       # responses served by a fallback model

    def record(self, role: str, model: str, usage) -> None:
        key = (role, model)
        s = self.spend.setdefault(key, ModelSpend())
        s.calls += 1
        s.input_tokens += usage.input_tokens or 0
        s.output_tokens += usage.output_tokens or 0
        s.cache_write_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        s.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        s.cost_usd += usage_cost_usd(model, usage)

    @property
    def total_cost_usd(self) -> float:
        return sum(s.cost_usd for s in self.spend.values())

    @property
    def total_tokens(self) -> dict:
        return {
            "input": sum(s.input_tokens for s in self.spend.values()),
            "output": sum(s.output_tokens for s in self.spend.values()),
            "cache_write": sum(s.cache_write_tokens for s in self.spend.values()),
            "cache_read": sum(s.cache_read_tokens for s in self.spend.values()),
        }

    def to_dict(self) -> dict:
        return {
            "cost_usd": round(self.total_cost_usd, 4),
            "tokens": self.total_tokens,
            "lead_turns": self.lead_turns,
            "sidekick_turns": self.sidekick_turns,
            "lead_code_edits": self.lead_code_edits,
            "delegations": self.delegations,
            "first_delegation_turn": self.first_delegation_turn,
            "refusals": self.refusals,
            "fallbacks_served": self.fallbacks_served,
            "by_role_model": {
                f"{role}/{model}": {
                    "calls": s.calls,
                    "input_tokens": s.input_tokens,
                    "output_tokens": s.output_tokens,
                    "cache_write_tokens": s.cache_write_tokens,
                    "cache_read_tokens": s.cache_read_tokens,
                    "cost_usd": round(s.cost_usd, 4),
                }
                for (role, model), s in self.spend.items()
            },
        }
