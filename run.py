#!/usr/bin/env python3
"""Run a single (task, config) session and print the metrics.

    python run.py --task lru_cache --config fable+haiku
    python run.py --task partial-refund-cent-loss --config fable+haiku --driver cc
    python run.py --task rate_limiter --config opus-solo --keep-workspace

Drivers:
    api  (default) — raw Anthropic API via the harness's own agent loop.
                     Needs ANTHROPIC_API_KEY / API credits.
    cc             — headless Claude Code session on your Claude subscription.
                     Lead = --model, sidekick = a subagent pinned to the cheap
                     model. Cost in the metrics is notional (API prices applied
                     to the tokens actually used). Runs are logged with the
                     config label "<config>@cc" so drivers never mix in
                     comparisons.
"""

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

from harness.agents import Session
from harness.cc_driver import run_cc_session
from harness.configs import CONFIGS
from harness.llm import make_client
from harness.metrics import Ledger
from harness.scoring import list_tasks, load_task, make_run_workspace, score_workspace
from harness.tools import Workspace

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Oracle-contamination scan (rl-environments skill step 4b): for post-cutoff
# real-repo tasks, upstream HEAD / PyPI contain the fix or feature. Any of
# these in a transcript means the run must be audited before its score is
# trusted; a confirmed upstream fetch excludes the score entirely.
CONTAMINATION_PATTERNS = [
    r"raw\.githubusercontent\.com",
    r"git\s+(clone|fetch|pull)",
    r"pip\s+install\s+(?!-e\b|\.\[|\"\.|'\.)[a-zA-Z]",  # installing a named pkg (not -e .)
    r"pip\s+download",
    r"gh\s+(pr|api|repo)",
]


def scan_contamination(transcript_path: Path) -> list[str]:
    import re
    try:
        text = transcript_path.read_text()
    except OSError:
        return []
    hits = []
    for pattern in CONTAMINATION_PATTERNS:
        found = re.findall(pattern, text)
        if found:
            hits.append(f"{pattern} x{len(found)}")
    return hits


def run_one(task_name: str, config_name: str, *, driver: str = "api",
            delegation_prompt: str = "neutral",
            verbose: bool = True, keep_workspace: bool = False) -> dict:
    task = load_task(task_name)
    config = CONFIGS[config_name]
    workspace_root = make_run_workspace(task)

    started = time.time()
    label = config_name if driver == "api" else f"{config_name}@cc"
    if driver == "cc" and delegation_prompt in ("push", "fanout"):
        label += f"-{delegation_prompt}"
    stem = f"{task_name}__{label}__{int(started)}"
    RESULTS_DIR.mkdir(exist_ok=True)
    transcript_path = RESULTS_DIR / f"{stem}.transcript.jsonl"

    error = None
    summary = ""

    if driver == "cc":
        metrics = run_cc_session(
            task_prompt=task.prompt,
            workspace_root=workspace_root,
            lead_model=config.lead_model,
            sidekick_model=config.sidekick_model,
            transcript_path=transcript_path,
            prompt_variant=delegation_prompt,
            verbose=verbose,
        )
        summary = metrics.pop("lead_summary", "")
        error = metrics.pop("error", None)
    else:
        ledger = Ledger()
        session = Session(
            make_client(),
            Workspace(workspace_root),
            ledger,
            lead_model=config.lead_model,
            sidekick_model=config.sidekick_model,
            lead_effort=config.lead_effort,
            sidekick_effort=config.sidekick_effort,
            verbose=verbose,
        )
        try:
            summary = session.run_lead(task.prompt)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        with transcript_path.open("w") as f:
            for entry in session.transcript:
                f.write(json.dumps(entry, default=str) + "\n")
        metrics = ledger.to_dict()

    wall_s = round(time.time() - started, 1)
    contamination = scan_contamination(transcript_path)

    # Archive the diff BEFORE scoring/cleanup — grader QA needs to read the
    # fix when a score looks wrong (house rule from rl-environments).
    diff_path = RESULTS_DIR / f"{stem}.diff"
    src = task.path / ("workspace" if task.kind == "local" else "world")
    diff_proc = subprocess.run(
        ["diff", "-ruN", "-x", ".venv", "-x", "__pycache__", "-x", ".pytest_cache",
         "-x", ".git", "-x", ".claude", "-x", "*.egg-info", "-x", ".coverage*",
         str(src), str(workspace_root)],
        capture_output=True)  # bytes: agent workspaces can contain binary files
    diff_text = diff_proc.stdout.decode("utf-8", errors="replace")
    # normalize to a/ b/ prefixes so `git apply -p1` works on the archive
    diff_text = diff_text.replace(str(src), "a").replace(str(workspace_root), "b")
    diff_path.write_text(diff_text)

    score = score_workspace(task, workspace_root)

    result = {
        "task": task_name,
        "config": label,
        "driver": driver,
        "lead_model": config.lead_model,
        "sidekick_model": config.sidekick_model,
        "score": score,
        "wall_seconds": wall_s,
        "error": error,
        "lead_summary": summary,
        "transcript": str(transcript_path),
        "contamination_hits": contamination,
        **metrics,
    }
    if contamination:
        print(f"\n⚠ CONTAMINATION AUDIT NEEDED — transcript matched: {contamination}\n"
              f"  (an upstream fetch of the task repo invalidates the score)",
              flush=True)

    out = RESULTS_DIR / f"{stem}.json"
    out.write_text(json.dumps(result, indent=2))

    if keep_workspace:
        result["workspace"] = str(workspace_root)
    else:
        shutil.rmtree(workspace_root, ignore_errors=True)
    return result


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", required=True, choices=list_tasks())
    parser.add_argument("--config", required=True, choices=sorted(CONFIGS))
    parser.add_argument("--driver", choices=["api", "cc"], default="api")
    parser.add_argument("--delegation-prompt", choices=["neutral", "push", "fanout"],
                        default="neutral",
                        help="cc driver only: neutral leaves delegation to the "
                             "model's judgment; push adds explicit triggers "
                             "(runs are labeled <config>@cc-push)")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--keep-workspace", action="store_true")
    args = parser.parse_args()

    result = run_one(args.task, args.config, driver=args.driver,
                     delegation_prompt=args.delegation_prompt,
                     verbose=not args.quiet, keep_workspace=args.keep_workspace)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
