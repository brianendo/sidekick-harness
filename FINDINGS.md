# Findings — lead/sidekick delegation experiments

*2026-07-16 → 2026-07-20. A minimal replication and extension of Cognition's
["Making Fable cheaper than Opus"](https://cognition.com/blog/making-fable-cheaper-than-opus),
run on tasks from the sibling [`rl-environments`](../rl-environments) project
(planted-truth worlds, verifier-owned graders). All agent runs via headless
Claude Code on a Max subscription; costs are notional (API list prices applied
to actual token usage). **Every cell below is n=1** — directional, not
confirmatory.*

---

## 1. Delegation count follows task structure, not prompt pressure

The starting observation: across every early run, the lead delegated exactly
**once**, always synchronously. Was that model reluctance, prompt framing, or
correct judgment? A three-cell ablation separated the variables:

| Cell | Task structure | Prompt | Delegations | Score | Cost | Wall |
|---|---|---|---|---|---|---|
| pandera @push | coupled units | singular phrasing | 1 | 1.00 | $11.72 | 21 min |
| pandera @fanout | coupled units | parallelism explicitly licensed | **1** | 1.00 | $6.44 | 16 min |
| milestone @fanout | 3 independent epics | parallelism licensed | **3 — in one message** | 1.00 | $5.73 | 10 min |

- On a task whose units genuinely couple (pandera's io/inference/pydantic all
  depend on the core schema classes), an explicit license for parallel
  background sidekicks changed nothing: still one brief. The model declined
  the invitation where fan-out would be wrong.
- On a task with three truly independent workstreams
  (`marketplace-q3-milestone`), the same lead investigated ~10 turns, built
  the shared foundation itself, then issued **all three epic briefs in a
  single assistant message** — true parallel fan-out, each brief carrying
  explicit file boundaries ("do not write anywhere in exports/ except
  exports/webhook_outbox/"). Three features shipped at 1.00 in 10 minutes.

**Conclusion:** Fable delegates exactly as much as the task's real dependency
structure makes rational. The low delegation counts were correctness, not
reluctance.

## 2. Delegation economics: unit depth vs. shared context, not task size

All four solo-vs-delegation cost pairs, identical score (1.00 unless noted):

| Task | Solo | Best delegation | Winner |
|---|---|---|---|
| vendor-statements (1 shallow epic) | $2.75 / 5 min | $3.20 @push / 9 min | solo |
| celery-worker-stall (1 deep fix) | $5.20 / 15 min | $4.94 @push / 12 min | delegation |
| pandera (1 deep feature) | $12.76 | **$6.44 @fanout / 16 min (−50%)** | delegation |
| marketplace-q3-milestone (3 shallow epics) | **$4.58 / 8 min** | $5.73 @fanout / 10 min | solo |

The naive law ("delegation benefit scales with task size") was falsified by
the milestone row — three features, and solo still won. The law that fits all
four points: **delegation pays when the delegable unit is deep relative to the
shared context; it loses when units are shallow and lean on one shared
understanding.** On pandera the delegated unit was 67+ turns of
implementation — the sidekick's cheaper rates on that depth dominate. On the
milestone, three ~100-line scripts hang off one insight (recorded ledger lines
are authoritative + one canonicalization pattern); a solo lead learns the
world once and stamps out three implementations with heavy prompt-cache
reuse, while fan-out pays three context establishments plus brief-writing and
review. This generalizes the limitation Cognition's blog states for serial
debugging ("accumulated context *is* the work"): shared context favors a
single holder, however many units hang off it.

Delegation retains two wins even where it costs more: **lead code edits**
(milestone: 18 solo → 1 with fan-out — the lead's attention is often the
scarcer resource) and wall-clock parallelism on deep independent units.

## 3. Fable vs. Opus as lead (the original blog's axis)

On celery-worker-stall-after-reconnect (real-repo debugging, hidden
contract tests):

| Config | Score | Cost | Lead turns | Corrective edits | Core contract |
|---|---|---|---|---|---|
| fable-solo | 1.00 | $5.20 | 31 | 2 | ✅ |
| opus-solo | 0.50 | $10.75 | 103 | 14 | ❌ |

Fable was **cheaper than Opus before any sidekick entered** — half the cost,
double the score. Opus's failure mode matches the blog's mechanism: 3× the
turns, 7× the corrective edits at lead prices, 12.4M cache-read tokens of
re-reading, and it still missed the accepted-vs-never-accepted invariant that
the hidden contract tests enforce. (Opus cells on the newer tasks are not yet
run.)

## 4. How Fable actually briefs: executable contracts

Transcript-level observations, consistent across delegation runs:

- **Test-first delegation.** On pandera, the lead *wrote the failing
  acceptance test file itself*, then briefed the sidekick with "making this
  failing test file pass, without weakening it, is the definition of done"
  plus architecture constraints. The brief is machine-checkable, not prose —
  arguably stronger than the constraint-brief style the blog describes.
- **Zero corrective edits.** In every delegation run, the lead never touched
  the sidekick's implementation code. Its own edits were acceptance tests and
  docs (a metric split worth making: authoring vs. correcting).
- **Foundation-first fan-out.** On the milestone, the lead built the shared
  foundation before issuing the three parallel briefs — interface-first
  decomposition, unprompted.
- The push/fanout prompts did not change *whether* correct judgment happened,
  but the contract-first framing correlated with cheaper runs (pandera:
  $11.72 push → $6.44 fanout at equal score; n=1, unconfirmed).

## 5. Meta-finding: the grader-QA discipline caught every real bug

Three times, a surprising score was grader error, and the rl-environments
house rules (first run is grader QA; read the fix before believing a low
score; second-valid-implementation gate) caught it before it became a wrong
conclusion:

1. pandera v1 scored a valid run 0.70 — gradevenv lacked pyyaml (the agent's
   yaml test was correct) and repro counted a collection-error as one failure.
   Fixed → 1.00; original preserved in the run JSON.
2. vendor-statements' line-subsequence "untampered" check scored the
   *canonical maintainer PR* 0.95 — removed in favor of grading against
   pristine tests (which makes tampering pointless anyway).
3. The second-valid-implementation gate on pandera initially failed on
   `BackendNotFoundError` — a real implementation requirement (registry keyed
   by schema class), not grader coupling; hidden tests passed 9/9 once the
   variant registered its backends.

Also built along the way: **oracle-contamination scanning** on every run
(post-cutoff tasks have their fix on upstream HEAD and PyPI) — all scored
runs audited clean.

## Method notes & caveats

- **Driver**: headless Claude Code (`claude -p`), hermetic sessions
  (`--setting-sources ""`), sidekick as a pinned subagent via `--agents`.
  This measures "Claude Code the product" (its Task/Agent machinery), not a
  bare-model loop; an API driver exists in this repo for the bare-loop
  version but was blocked on credits.
- **Costs are notional**: API list prices applied to measured tokens
  (Claude Code's own figures differ slightly via 1h-cache pricing).
  Consistent within the harness, so comparisons hold.
- **n=1 everywhere.** Observed run-to-run variance elsewhere (fable 1.00 vs
  0.50 on the same celery task) means every number above needs repeats
  before strong claims. The two headline cells to repeat first:
  milestone@fanout and pandera@fanout.
- All runs, transcripts, diffs, and per-checkpoint grader reports are in
  `results/` (aggregate with `python compare.py --task <task>`).

## Reproduce

```bash
python run.py --task marketplace-q3-milestone --config fable+sonnet \
  --driver cc --delegation-prompt fanout
python run.py --task marketplace-q3-milestone --config fable-solo --driver cc
python compare.py --task marketplace-q3-milestone
```

Tasks live in `../rl-environments/tasks/` (auto-discovered). Task-side QA:
each task's `qa/qa.py` and CHANGELOG record its gates and post-mortems.
