"""Claude Code driver — run lead/sidekick sessions on a Claude subscription.

Instead of the raw API (which needs credits), this drives a headless
`claude -p` session in the workspace. The lead runs on the config's lead
model; the sidekick is a Claude Code subagent pinned to the sidekick model,
delegated to via the built-in Task tool. The stream-json transcript carries
per-message model + usage, so the same Ledger metrics are computed — cost is
*notional* (what the tokens would cost at API prices), which keeps
comparisons apples-to-apples with API-driver runs.

Differences vs the API driver to keep in mind when comparing:
- Claude Code's own system prompt and tool set (Read/Write/Edit/Bash/Task...)
  replace the harness's minimal tools; behavior is "Claude Code the product",
  not a bare model loop.
- No per-role effort control.
- Delegation = Task calls to the `sidekick` agent; the lead may also use
  built-in agents (counted separately as `other_subagent_calls`).
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from .metrics import Ledger

CC_TIMEOUT_S = 2400

# Subagent `model` field is documented as an alias (sonnet/opus/haiku);
# map full IDs, pass anything unknown through.
_AGENT_MODEL_ALIAS = {
    "claude-haiku-4-5": "haiku",
    "claude-sonnet-5": "sonnet",
    "claude-opus-4-8": "opus",
}

LEAD_APPEND = """Economics: your tokens are expensive. You have a `sidekick` subagent — a cheaper, capable model working in this same workspace — available through the Task tool. Delegating implementation work to it is usually far cheaper than doing it yourself; it is your call when delegation fits the task.

When you delegate, write the brief like a spec: the goal, the constraints that must hold, and how success will be verified — not the exact code to type. Review the sidekick's work by inspecting the changed files or running the verification you specified. If something is wrong, prefer re-delegating a fix with a corrected brief over editing code yourself.

Work only inside the current directory. Finish with a short summary of what was done and how it was verified."""

LEAD_APPEND_PUSH = """Economics: your tokens are expensive. You have a `sidekick` subagent — a cheaper, capable model working in this same workspace — available through the Task tool. Delegate deliberately:

- Once you have diagnosed a root cause, delegate the implementation to the sidekick with a constraint-based brief — the goal, the invariants that must hold, and how success will be verified — rather than writing the code yourself. Do not dictate exact code.
- Delegate self-contained side-quests that don't need your accumulated context: building a repro script, sweeping a test suite, reconciling data, writing regression tests for a contract you specify.
- Keep for yourself only work where each step depends on context you alone have built up (serial debugging of a live hypothesis).

Review the sidekick's work by running the verification you specified in the brief. If something is wrong, re-delegate a fix with a corrected brief instead of editing code yourself.

Work only inside the current directory. Finish with a short summary of what was done and how it was verified."""

LEAD_APPEND_SOLO = """Work only inside the current directory. Finish with a short summary of what was done and how it was verified."""

LEAD_APPEND_FANOUT = """Economics: your tokens are expensive. You have a `sidekick` subagent — a cheaper, capable model working in this same workspace — available through the Task tool, and you may run SEVERAL sidekick tasks AT ONCE (run_in_background=true, then collect results).

Work like a tech lead running a team:
- Do the judgment work yourself first: understand the task, pin the contract (writing failing acceptance tests yourself is an excellent brief), and decide the architecture.
- Then DECOMPOSE the implementation into independent units with explicit file boundaries — which files each unit owns — and delegate EACH unit as its own sidekick task, in parallel wherever units don't depend on each other. Sequence only what truly depends on another unit's output. Sidekicks cannot see each other's work in progress: partition files so they never edit the same file.
- Each brief: the unit's goal, the constraints that must hold, its file boundary, and how success will be verified. Do not dictate exact code.
- Integrate and verify yourself. If a unit is wrong, re-delegate a fix with a corrected brief instead of editing code yourself.

Work only inside the current directory. Finish with a short summary of what was done and how it was verified."""

SIDEKICK_PROMPT = """You are an implementation engineer working in a shared workspace. You receive a brief from the lead engineer. Complete exactly what the brief asks: honor every stated constraint, verify your work (run the code or tests where possible), and do not expand scope beyond the brief.

Finish with a concise report: what you changed, how you verified it, and anything the lead should double-check."""


def run_cc_session(
    *,
    task_prompt: str,
    workspace_root: Path,
    lead_model: str,
    sidekick_model: str | None,
    transcript_path: Path,
    prompt_variant: str = "neutral",  # "neutral" | "push"
    verbose: bool = True,
) -> dict:
    """Run one headless Claude Code session. Returns metrics + summary."""
    cmd = [
        "claude", "-p", task_prompt,
        "--model", lead_model,
        # Hermetic run: skip user/project/local settings (plugins, custom
        # agents, hooks) — otherwise the lead sees dozens of unrelated agents
        # and the sidekick drowns. NOTE: --safe-mode also drops --agents, and
        # --bare drops keychain auth; --setting-sources "" keeps both.
        "--setting-sources", "",
        "--permission-mode", "acceptEdits",
        "--allowedTools", "Bash",
        "--output-format", "stream-json",
        "--verbose",
    ]
    if sidekick_model is not None:
        agents = {
            "sidekick": {
                "description": (
                    f"Implementation engineer running on {sidekick_model} — "
                    "much cheaper than you. Delegate well-scoped implementation "
                    "or investigation work with a spec-style brief."
                ),
                "prompt": SIDEKICK_PROMPT,
                "model": _AGENT_MODEL_ALIAS.get(sidekick_model, sidekick_model),
            }
        }
        cmd += ["--agents", json.dumps(agents)]
    if sidekick_model is None:
        append = LEAD_APPEND_SOLO
    else:
        append = {"push": LEAD_APPEND_PUSH, "fanout": LEAD_APPEND_FANOUT}.get(
            prompt_variant, LEAD_APPEND)
    cmd += ["--append-system-prompt", append]

    # Make sure the CLI bills the subscription, not an API key.
    env = os.environ.copy()
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(var, None)

    if verbose:
        print(f"  [cc] claude -p ... --model {lead_model}"
              + (f" (sidekick={sidekick_model})" if sidekick_model else " (solo)"),
              file=sys.stderr, flush=True)

    with transcript_path.open("w") as out:
        try:
            proc = subprocess.run(
                cmd, cwd=workspace_root, stdout=out, stderr=subprocess.PIPE,
                text=True, timeout=CC_TIMEOUT_S, env=env,
            )
            agent_exit, stderr_tail = proc.returncode, proc.stderr[-2000:]
        except subprocess.TimeoutExpired:
            agent_exit, stderr_tail = -1, f"timed out after {CC_TIMEOUT_S}s"

    metrics = parse_transcript(transcript_path, sidekick_model=sidekick_model,
                               verbose=verbose)
    metrics["agent_exit_code"] = agent_exit
    if agent_exit != 0:
        metrics["error"] = metrics.get("error") or f"claude exit {agent_exit}: {stderr_tail}"
    return metrics


def parse_transcript(transcript_path: Path, sidekick_model: str | None = None,
                     verbose: bool = False) -> dict:
    """Compute Ledger-equivalent metrics from a stream-json transcript.

    Token/cost truth comes from the result event's `modelUsage` (per-model
    totals — authoritative; per-message usage snapshots undercount output).
    Role attribution: the sidekick model's usage is the sidekick's — lead and
    sidekick are always distinct models in our configs. Per-message events are
    still walked for structure: turns, delegations, lead edits.
    """
    ledger = Ledger()
    per_message: dict[str, tuple[str, str, dict]] = {}  # mid -> (role, model, usage)
    model_usage: dict = {}
    seen_tool_use_ids: set[str] = set()
    other_subagent_calls = 0
    summary = ""
    reported_cost = None
    error = None

    for line in transcript_path.read_text().splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if obj.get("type") == "assistant":
            msg = obj.get("message", {})
            role = "sidekick" if obj.get("parent_tool_use_id") else "lead"
            mid = msg.get("id")
            if mid:
                per_message[mid] = (role, msg.get("model", "unknown"), msg.get("usage") or {})

            for block in msg.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                bid = block.get("id")
                if role != "lead" or (bid and bid in seen_tool_use_ids):
                    continue
                if bid:
                    seen_tool_use_ids.add(bid)
                name = block.get("name", "")
                lead_turn = sum(1 for r, _, _ in per_message.values() if r == "lead")
                if name in ("Task", "Agent"):  # delegation tool: "Task" pre-2.1 CLI, "Agent" since
                    subagent = (block.get("input") or {}).get("subagent_type", "")
                    if subagent == "sidekick":
                        ledger.delegations += 1
                        if ledger.first_delegation_turn is None:
                            ledger.first_delegation_turn = lead_turn
                    else:
                        other_subagent_calls += 1
                elif name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
                    ledger.lead_code_edits += 1
                if verbose:
                    print(f"  [cc {role}] {name} "
                          f"{str(block.get('input'))[:100]}", file=sys.stderr, flush=True)

        elif obj.get("type") == "result":
            summary = obj.get("result") or ""
            reported_cost = obj.get("total_cost_usd")
            model_usage = obj.get("modelUsage") or {}
            if obj.get("is_error"):
                error = f"result subtype={obj.get('subtype')}"

    # Turn counts from the message walk.
    ledger.lead_turns = sum(1 for r, _, _ in per_message.values() if r == "lead")
    ledger.sidekick_turns = sum(1 for r, _, _ in per_message.values() if r == "sidekick")

    if model_usage:
        # Authoritative per-model totals from the result event.
        for model, mu in model_usage.items():
            role = "sidekick" if sidekick_model and model.startswith(sidekick_model) else "lead"
            ledger.record(role, model, SimpleNamespace(
                input_tokens=mu.get("inputTokens", 0),
                output_tokens=mu.get("outputTokens", 0),
                cache_creation_input_tokens=mu.get("cacheCreationInputTokens", 0),
                cache_read_input_tokens=mu.get("cacheReadInputTokens", 0),
            ))
    else:
        # Fallback (session died before the result event): last per-message
        # usage snapshots — output tokens will undercount.
        for role, model, usage in per_message.values():
            ledger.record(role, model, SimpleNamespace(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
                cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
            ))

    out = ledger.to_dict()
    out["other_subagent_calls"] = other_subagent_calls
    out["cc_reported_cost_usd"] = reported_cost
    out["lead_summary"] = summary
    out["error"] = error
    return out
