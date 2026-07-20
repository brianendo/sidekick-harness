#!/usr/bin/env python3
"""Run the task x config matrix and write a comparison table.

    python run_experiment.py                                  # default matrix
    python run_experiment.py --configs fable+haiku opus+haiku --tasks lru_cache
    python run_experiment.py --repeats 3

Produces results/summary.md with the same shape as Cognition's table:
score / cost / lead turns / input tokens / lead edits / delegation timing.
"""

import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

from harness.configs import CONFIGS
from harness.scoring import list_tasks
from run import RESULTS_DIR, run_one

DEFAULT_CONFIGS = ["fable+haiku", "fable+sonnet", "opus+haiku", "opus+sonnet",
                   "fable-solo", "opus-solo"]
# Only the built-in toy tasks by default. rl-environments tasks are discovered
# and runnable by name (e.g. --tasks partial-refund-cent-loss), but their
# worlds may need extra deps in this venv — opt in explicitly.
DEFAULT_TASKS = ["lru_cache", "rate_limiter", "word_index"]


def summarize(rows: list[dict]) -> str:
    by_config: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_config[r["config"]].append(r)

    lines = [
        "| Config | Runs | Score | Cost/run | Lead turns | Input tokens | Lead edits | Delegations | 1st delegation turn |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for config, runs in sorted(by_config.items()):
        scores = [r["score"]["score"] for r in runs]
        costs = [r["cost_usd"] for r in runs]
        lead_turns = [r["lead_turns"] for r in runs]
        input_toks = [
            r["tokens"]["input"] + r["tokens"]["cache_write"] + r["tokens"]["cache_read"]
            for r in runs
        ]
        edits = [r["lead_code_edits"] for r in runs]
        delegations = [r["delegations"] for r in runs]
        first_del = [r["first_delegation_turn"] for r in runs if r["first_delegation_turn"]]
        first_del_str = f"{statistics.mean(first_del):.1f}" if first_del else "—"
        lines.append(
            f"| {config} | {len(runs)} "
            f"| {statistics.mean(scores):.2f} "
            f"| ${statistics.mean(costs):.3f} "
            f"| {statistics.mean(lead_turns):.1f} "
            f"| {statistics.mean(input_toks) / 1000:.0f}k "
            f"| {statistics.mean(edits):.1f} "
            f"| {statistics.mean(delegations):.1f} "
            f"| {first_del_str} |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", nargs="+", default=DEFAULT_TASKS, choices=list_tasks())
    parser.add_argument("--configs", nargs="+", default=DEFAULT_CONFIGS,
                        choices=sorted(CONFIGS))
    parser.add_argument("--driver", choices=["api", "cc"], default="api")
    parser.add_argument("--delegation-prompt", choices=["neutral", "push", "fanout"], default="neutral")
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()

    rows = []
    total = len(args.tasks) * len(args.configs) * args.repeats
    i = 0
    for repeat in range(args.repeats):
        for task in args.tasks:
            for config in args.configs:
                i += 1
                print(f"\n=== [{i}/{total}] {task} x {config} (repeat {repeat + 1}) ===")
                try:
                    result = run_one(task, config, driver=args.driver,
                                     delegation_prompt=args.delegation_prompt,
                                     verbose=True)
                except Exception as e:
                    print(f"RUN FAILED: {e}")
                    continue
                rows.append(result)
                print(f"  score={result['score']['score']} cost=${result['cost_usd']:.3f} "
                      f"lead_turns={result['lead_turns']} edits={result['lead_code_edits']} "
                      f"delegations={result['delegations']}")

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = int(time.time())
    (RESULTS_DIR / f"experiment_{stamp}.json").write_text(json.dumps(rows, indent=2))

    table = summarize(rows)
    header = (
        f"# Experiment {stamp}\n\n"
        f"Tasks: {', '.join(args.tasks)} · repeats: {args.repeats}\n\n"
    )
    (RESULTS_DIR / "summary.md").write_text(header + table + "\n")
    print("\n" + table)
    print(f"\nWrote results/experiment_{stamp}.json and results/summary.md")


if __name__ == "__main__":
    main()
