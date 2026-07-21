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

*Variance note:* on `marketplace-quarter-close` (same 3-independent-epic
structure, same fanout prompt), the lead again delegated all three epics but
issued the briefs **sequentially** — one per message — so there was no
wall-clock win. Whether fan-out parallelizes appears to be run-level
variance, not a stable property of the task structure (n=1 each way).

*A third delegation mode:* on `anyio-start-task-handles` (deep, *invasive*
real-repo feature — core concurrency machinery across two backends), the
fanout-prompted lead delegated **zero implementation**: it made all 37 edits
itself over ~180 turns, then issued exactly one brief at the very end — a
**read-only code review** ("Do NOT modify any files — report findings
only"). Delegation-as-verification, unprompted. The structure-following
conclusion holds in a stronger form: on work that is serial all the way
down, the lead keeps the accumulated context and outsources only the one
task that benefits from fresh eyes.

## 2. Delegation economics: it's where the tokens go, not unit depth

All six solo-vs-delegation cost pairs, identical score (1.00 unless noted):

| Task | Solo | Best delegation | Winner |
|---|---|---|---|
| vendor-statements (1 shallow epic, owned world) | $2.75 / 5 min | $3.20 @push / 9 min | solo |
| celery-worker-stall (1 deep fix, real repo) | $5.20 / 15 min | $4.94 @push / 12 min | delegation |
| pandera (1 deep **additive** feature, real repo) | $12.76 | **$6.44 @fanout / 16 min (−50%)** | delegation |
| marketplace-q3-milestone (3 shallow epics, owned world) | **$4.58 / 8 min** | $5.73 @fanout / 10 min | solo |
| marketplace-quarter-close (3 **deep** epics, owned world) | **$5.21 / 10 min** | $6.35 @fanout / 11 min | solo |
| anyio-start-task-handles (1 deep **invasive** feature, real repo) | **$17.95 / 31 min** | $22.06 @fanout / 38 min | solo |

Two laws died in sequence here. "Delegation benefit scales with task size"
was falsified by the milestone row. Its replacement — "delegation pays when
the delegable unit is *deep*" — we then falsified deliberately:
`marketplace-quarter-close` keeps the milestone's 3-way epic independence but
makes each epic a spec-heavy mini-project (a rule engine, a reconciliation
matcher, a hash-chain CLI — the sidekick wrote ~730 lines of implementation
plus ~800 lines of its own tests, 70k output tokens). Deep units, fully
delegated (all 3 epics, 1 lead edit) — and solo *still* won by $1.14.

The token decomposition says why, and gives the law that fits all six
points: **delegation pays exactly when it removes token mass from the lead —
and code emission against a spec the lead already holds is not removable.**
On quarter-close, delegating every implementation cut the lead's output only
53k → 37k (−$0.90): briefing three epics ≈ restating the spec it already
held, then reviewing and verifying the results. Meanwhile the sidekick spent
70k output tokens — more than the entire solo run — on the same three
scripts, and total output *doubled*. What made pandera different: the deep
unit there was **context acquisition and debug iteration inside a large real
repo** — exploration and test-fix loops the lead skipped entirely, token
mass that never touched fable's meter. Spec-transfer depth doesn't delegate
profitably; discovery depth does. (Cognition's blog gates delegation on
whether *accumulated context* is the work — this is that rule's economic
mirror image: delegation profits precisely on the context the lead never has
to accumulate.)

The anyio row then bounds the law from the other side: discovery depth is
necessary but **not sufficient** — the deep unit must also be *separable
after diagnosis*. anyio-start-task-handles was built as a pandera-class
replication probe (deep real-repo feature, discovery-heavy), but where
pandera's feature was **additive** (a new GeoDataFrame layer the lead could
spec at turn 22 and hand off), anyio's is **invasive** — it rewires core
spawn machinery across two backends, where every edit interacts with cancel
scopes, exception-group shapes, eager task factories, and ~650 existing
tests. The lead's (rational, per §1) response was to delegate no
implementation at all: its own token spend matched the solo run almost
exactly (105k vs 107k output), and the sidekick's $2.14 review — plus the
lead-side tokens spent consuming it — was pure overhead at equal score.
When the lead won't hand off the unit, the economics never get to run.

So the delegation-wins regime, as currently mapped: **a unit that is deep
(discovery/iteration-heavy), additive (separable once diagnosed), and
briefable as a contract** — pandera is the exemplar, celery the marginal
case — while both shallow units (overhead dominates) and invasive units
(the lead correctly keeps them) go to solo. Narrower than we hoped when
setting out to "prove delegation is cheaper," and worth stating honestly:
2 of 6 pairs favor delegation, and the structural preconditions are
identifiable in advance.

Delegation retains two wins even where it costs more: **lead code edits**
(milestone: 18 solo → 1 fan-out; quarter-close: 10 solo → 1) — the lead's
attention is often the scarcer resource — wall-clock parallelism when
fan-out actually runs in parallel (see §1 note), and the unprompted
**review-only delegation** on anyio, which is the blog's "fresh eyes"
pattern emerging without being asked for.

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
  the sidekick's implementation code. Its own edits were acceptance tests,
  docs, and scaffolding (quarter-close: the lead's single "edit" was writing
  `scripts/__init__.py`) — a metric split worth making: authoring vs.
  correcting.
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
  0.50 on the same celery task; parallel vs sequential fan-out on identical
  structure+prompt) means every number above needs repeats before strong
  claims. The headline cells to repeat first: pandera@fanout,
  quarter-close@fanout, milestone@fanout.
- **The delegation-wins side of the law rests on TWO pairs** (pandera −50%,
  celery −$0.26) after two replication attempts landed solo-side for
  structurally-diagnosable reasons (quarter-close: spec-transfer depth;
  anyio: invasive unit, lead declined to hand off). Next probes, in order of
  information value: (1) repeat pandera@fanout — the −50% is the load-bearing
  cell and it is n=1; (2) harvest another deep **additive** real-repo
  feature (new module/subsystem layer, clean seam after diagnosis) — the
  regime the law now predicts delegation wins; (3) an opus-lead cell on
  anyio to see whether weaker judgment delegates the invasive unit anyway,
  and what that costs.
- **anyio contamination note**: the fanout run's scanner hits were audited
  benign — the flagged `pip download anyio==4.11.0` fetched a release two
  minors OLDER than the world (cannot contain the fix; the unpinned
  fallback never executed), and the greps against it targeted names from
  the agent's own diff. Zero upstream git/GitHub fetches in either run.
- All runs, transcripts, diffs, and per-checkpoint grader reports are in
  `results/` (aggregate with `python compare.py --task <task>`).

## Reproduce

```bash
python run.py --task marketplace-quarter-close --config fable+sonnet \
  --driver cc --delegation-prompt fanout
python run.py --task marketplace-quarter-close --config fable-solo --driver cc
python compare.py --task marketplace-quarter-close
```

Tasks live in `../rl-environments/tasks/` (auto-discovered). Task-side QA:
each task's `qa/qa.py` and CHANGELOG record its gates and post-mortems.
