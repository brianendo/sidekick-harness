#!/usr/bin/env python3
"""Compare archived runs across configs.

Every run.py / run_experiment.py invocation logs a per-run JSON (metrics +
checkpoint breakdown) and a .transcript.jsonl under results/. This rolls
those logs into a comparison:

    python compare.py --task partial-refund-cent-loss
    python compare.py --task partial-refund-cent-loss --configs fable+haiku fable+sonnet opus+haiku opus+sonnet
    python compare.py                     # all tasks, grouped

Output: stdout + results/compare_<task>.md
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def load_runs(task: str | None, configs: list[str] | None) -> list[dict]:
    runs = []
    for f in sorted(RESULTS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict) or "config" not in data or "task" not in data:
            continue  # experiment_*.json aggregates etc.
        if task and data["task"] != task:
            continue
        if configs and data["config"] not in configs:
            continue
        data["_file"] = f.name
        runs.append(data)
    return runs


def _sidekick_cost(run: dict) -> float:
    return sum(
        v["cost_usd"] for k, v in run.get("by_role_model", {}).items()
        if k.startswith("sidekick/")
    )


def main_table(runs: list[dict]) -> str:
    by_config = defaultdict(list)
    for r in runs:
        by_config[r["config"]].append(r)

    lines = [
        "| Config | Runs | Score | Cost/run | Sidekick $ share | Lead turns | Lead edits | Delegations | 1st deleg. turn | Wall (s) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for config, rs in sorted(by_config.items(), key=lambda kv: -mean(r["score"]["score"] for r in kv[1])):
        costs = [r["cost_usd"] for r in rs]
        share = (
            f"{sum(_sidekick_cost(r) for r in rs) / sum(costs):.0%}"
            if sum(costs) > 0 and any(_sidekick_cost(r) for r in rs) else "—"
        )
        first_del = [r["first_delegation_turn"] for r in rs if r.get("first_delegation_turn")]
        lines.append(
            f"| {config} | {len(rs)} "
            f"| {mean(r['score']['score'] for r in rs):.2f} "
            f"| ${mean(costs):.3f} "
            f"| {share} "
            f"| {mean(r['lead_turns'] for r in rs):.1f} "
            f"| {mean(r['lead_code_edits'] for r in rs):.1f} "
            f"| {mean(r['delegations'] for r in rs):.1f} "
            f"| {f'{mean(first_del):.1f}' if first_del else '—'} "
            f"| {mean(r.get('wall_seconds') or 0 for r in rs):.0f} |"
        )
    return "\n".join(lines)


def checkpoint_matrix(runs: list[dict]) -> str | None:
    """Pass rate per grading checkpoint per config (rl-env tasks only)."""
    by_config = defaultdict(list)
    checkpoint_names: list[str] = []
    for r in runs:
        cps = r.get("score", {}).get("checkpoints")
        if cps:
            by_config[r["config"]].append(cps)
            for name in cps:
                if name not in checkpoint_names:
                    checkpoint_names.append(name)
    if not by_config:
        return None

    configs = sorted(by_config)
    lines = [
        "| Checkpoint | " + " | ".join(configs) + " |",
        "|---|" + "---|" * len(configs),
    ]
    for name in checkpoint_names:
        cells = []
        for config in configs:
            vals = [cps.get(name, False) for cps in by_config[config]]
            rate = sum(vals) / len(vals)
            cells.append({1.0: "✅", 0.0: "❌"}.get(rate, f"{rate:.0%}"))
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def run_log(runs: list[dict]) -> str:
    lines = ["| Run file | Config | Score | Cost | Error |", "|---|---|---|---|---|"]
    for r in sorted(runs, key=lambda r: r["_file"]):
        err = (r.get("error") or "")[:60]
        lines.append(
            f"| {r['_file']} | {r['config']} | {r['score']['score']:.2f} "
            f"| ${r['cost_usd']:.3f} | {err or '—'} |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", help="filter to one task")
    parser.add_argument("--configs", nargs="+", help="filter to these configs")
    args = parser.parse_args()

    runs = load_runs(args.task, args.configs)
    if not runs:
        print("No matching runs in results/. Run `python run.py --task ... --config ...` first.")
        return

    tasks = sorted({r["task"] for r in runs})
    sections = [f"# Comparison — {', '.join(tasks)} ({len(runs)} runs)\n"]
    sections.append("## By config\n\n" + main_table(runs))
    matrix = checkpoint_matrix(runs)
    if matrix:
        sections.append("\n## Checkpoint pass rates\n\n" + matrix)
    sections.append("\n## Runs (transcripts sit next to each file as *.transcript.jsonl)\n\n" + run_log(runs))
    report = "\n".join(sections) + "\n"

    out = RESULTS_DIR / f"compare_{args.task or 'all'}.md"
    out.write_text(report)
    print(report)
    print(f"-> wrote {out}")


if __name__ == "__main__":
    main()
