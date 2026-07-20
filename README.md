# sidekick-harness

A minimal, open replication of the lead/sidekick delegation architecture from
Cognition's ["Making Fable cheaper than Opus"](https://cognition.com/blog/making-fable-cheaper-than-opus):
an expensive frontier model **leads** a coding session — plans, delegates,
reviews, finishes — while a cheap model does the implementation. The harness
measures whether the lead's *judgment about delegation* (not its per-token
price) is what determines cost.

Cognition's headline result: Fable + sidekick ($1.86/run, score 60.7) beat
Opus + sidekick ($2.04/run, score 54.6) on FrontierCode 1.1, despite Fable
costing 2x per token — because Fable delegates on its first action, writes
constraint-based briefs instead of dictating code, and in 81% of runs never
makes a single code edit itself.

This repo reproduces that experimental setup at small scale so the behavioral
metrics behind the result can be observed directly on any lead/sidekick pair.

## Architecture

```
                 ┌──────────────────────────────────────────┐
 task spec ────► │ LEAD (fable-5 / opus-4.8 / sonnet-5)     │
                 │  plans · reviews diffs · verifies · ends │
                 └──────┬─────────────────────────▲─────────┘
                        │ delegate(brief)         │ report + changed files
                        ▼                         │
                 ┌──────────────────────────────────────────┐
                 │ SIDEKICK (haiku-4.5 / sonnet-5)          │
                 │  implements the brief autonomously       │
                 └──────────────────────────────────────────┘
                        both operate on the same sandboxed workspace
                        (read/write/edit files, run bash)
```

- **Lead** gets file tools + bash + a `delegate` tool. The system prompt states
  the economics ("your tokens are expensive; the sidekick is cheap") and leaves
  the delegation decision to the model — mirroring the blog, where the
  interesting variable is the lead's learned judgment.
- **`delegate(brief)`** spawns a full sidekick agent loop in the same
  workspace. The tool result is the sidekick's report plus a hash-diff of the
  files it changed.
- **Scoring** copies a hidden pytest suite into the workspace after the session
  ends. Score = fraction of tests passed. Each task carries an explicit
  performance constraint (e.g. "`get`/`put` must be O(1) — NO scanning") that a
  perf test enforces, so constraint-violating implementations lose points —
  the same failure mode the blog attributes to dictation-style briefs.

## Metrics per run

Everything Cognition's table reports, tracked natively:

| Metric | Why it matters (per the blog) |
|---|---|
| score, cost/run | the headline tradeoff |
| lead turns, input tokens | Opus burned 3x the input tokens of Fable |
| **lead code edits** | 81% of Fable runs: zero; Opus made 4x more corrective edits at lead prices |
| **delegations + first-delegation turn** | Fable delegates on its first action; Opus explores solo first |
| cost split by role/model | where the dollars actually went |

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

# one session
python run.py --task lru_cache --config fable+haiku

# the comparison matrix -> results/summary.md
python run_experiment.py --repeats 3

# roll ALL archived runs into a comparison (accumulates across sessions)
python compare.py --task partial-refund-cent-loss
```

Every run is logged permanently under `results/`: a per-run JSON (score,
checkpoint breakdown, cost split by role/model, delegation metrics) plus a
`.transcript.jsonl` trajectory. `compare.py` aggregates whatever has
accumulated — so you can run configs one at a time as budget allows and the
comparison keeps building.

Configs: `fable+haiku`, `fable+sonnet`, `opus+haiku`, `opus+sonnet`,
`sonnet+haiku`, and solo baselines (`fable-solo`, `opus-solo`, `sonnet-solo`,
`haiku-solo`). Tasks: `lru_cache`, `rate_limiter`, `word_index` — small enough
to run cheaply, each with a hidden test suite and a hard perf constraint.

## Running on a Claude subscription (no API credits)

`--driver cc` runs the session through a headless Claude Code CLI instead of
the raw API — billed to your Claude subscription:

```bash
python run.py --task partial-refund-cent-loss --config fable+haiku --driver cc
python run_experiment.py --driver cc --tasks partial-refund-cent-loss \
  --configs fable+haiku fable+sonnet opus+haiku opus+sonnet
```

The lead is the `claude -p` session on the config's lead model; the sidekick
is a Claude Code **subagent** pinned to the cheap model (passed via
`--agents`), delegated to through the built-in Task tool. Metrics come from
the stream-json transcript (per-message model + usage), with cost computed at
API list prices — *notional*, but apples-to-apples across configs.

Caveats: this measures "Claude Code the product" (its system prompt, tools,
and Task machinery), not the bare-model loop of the API driver — so cc runs
are labeled `<config>@cc` and never mix with API runs in `compare.py`. No
per-role effort control. Lead Task calls to built-in agents (Explore etc.)
are counted separately as `other_subagent_calls`.

## Implementation notes

- Per-model API handling lives in `harness/llm.py`: Fable 5 runs with
  always-on thinking (no `thinking` param) and **server-side refusal fallback
  to Opus 4.8** enabled by default; Opus/Sonnet use adaptive thinking; effort
  is configurable per role. Fallback-served turns are counted in the metrics
  so they can't silently skew a comparison.
- Cost accounting reads real `usage` off every response — including prompt
  cache reads/writes at their multipliers — and attributes cost to the model
  that actually served the response (`response.model`), so a Fable→Opus
  fallback bills as Opus.
- Incremental prompt caching across the agent loop: one moving cache
  breakpoint on the newest user turn plus a system-prompt breakpoint.
- Thinking blocks are echoed back verbatim in multi-turn history (required for
  Fable).

## rl-environments tasks (the real benchmark)

The built-in toy tasks are plumbing checks — too small for delegation
patterns to differentiate (the blog itself notes delegation shows minimal
benefit on short tasks). The real measurement runs on tasks from the sibling
[`rl-environments`](../rl-environments) project: investigation-heavy worlds
with a planted hidden truth, symptoms-only tickets, and shape-agnostic hidden
graders. Any directory under `~/Projects/rl-environments/tasks/` (override
with `RLENV_TASKS_DIR`) containing `task.md` + `world/` + `grade.py` is
auto-discovered and runnable by name:

```bash
python run.py --task partial-refund-cent-loss --config fable+haiku
```

- The prompt is `task.md` verbatim (behavioral voice, no added scaffolding).
- The workspace is a fresh copy of `world/` (never with git history).
- Scoring shells out to the task's own `grade.py` — weighted checkpoints,
  guarded-file restoration, hidden invariant tests. The checkpoint breakdown
  lands in the result JSON.
- Every run writes a `results/*.transcript.jsonl` trajectory — audit it for
  oracle-hunting before trusting a score (house rule inherited from
  rl-environments).

Validated wiring for `partial-refund-cent-loss`: untouched buggy world scores
0.40; the archived 1.00-scoring opus fix scores 1.00 through the adapter.
Other rl-env tasks (airflow, celery, pandera, ...) are discovered too, but
their worlds may need additional deps installed into this venv first.

Why this pairing matters: these tasks split cleanly into *investigation*
(surfacing the planted truth — the accumulated-context work the blog says
NOT to delegate) and *implementation under constraints* (where a
constraint-based brief either carries the discovered invariants or doesn't).
The hidden graders directly punish the dictation-style-brief failure mode;
the decoy stakeholder request tests whether pushback survives a handoff.

## Extending

- **Add a task:** `tasks/<name>/{task.json, workspace/spec.md, tests/test_*.py}`.
- **Add a pairing:** one line in `harness/configs.py`.
- Obvious next experiments: effort sweeps per role (`low` sidekick vs `high`),
  multiple sidekicks in parallel, brief-quality ablation (force
  dictation-style briefs and watch constraint violations return).
