# sidekick-harness — working instructions

Lead/sidekick delegation experiment harness. Read `README.md` (usage) and
`FINDINGS.md` (results so far) before changing anything; tasks come from
`../rl-environments/tasks/` (auto-discovered — that repo's CLAUDE.md rules
govern task/grader changes).

## Keep README.md and FINDINGS.md current

The repo is intended to go public eventually. Update in the same commit as
the change that affects them:
- **README** — any change to drivers, flags (`--driver`, `--delegation-prompt`),
  configs, logging/artifact layout, or the rl-environments adapter.
- **FINDINGS** — any completed experiment that adds, refines, or overturns a
  finding. Report honestly: keep falsified versions of claims in the text
  (as the milestone-solo row does for the "scales with size" claim), note
  n=1 cells as such, and link the run files in `results/` that back each
  number.

## House rules inherited from rl-environments

- A surprising score is grader QA first: read the run's `.diff` and the
  grader `tails` in the result JSON before believing it.
- Check `contamination_hits` on every rl-env task run; audit the transcript's
  pip/git commands before trusting a score.
- Fable runs spend real quota — prefer cheap configs (sonnet/haiku leads,
  toy tasks) when testing harness changes; `lru_cache` + `sonnet+haiku` is
  the standard smoke test.

## Commands

```bash
python run.py --task <task> --config <config> --driver cc [--delegation-prompt neutral|push|fanout]
python run_experiment.py --driver cc --tasks <t...> --configs <c...> --repeats N
python compare.py --task <task>          # aggregates ALL archived runs
python import_baseline.py <rl-env run dir>  # import archived solo runs
```
