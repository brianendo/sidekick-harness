#!/usr/bin/env python3
"""Import archived rl-environments run_agent.sh runs as baseline entries.

Those runs are headless `claude -p` solo sessions — the same thing the cc
driver produces with a solo config — so they slot into the comparison as
`<model>-solo@cc` rows. Cost/tokens are parsed from the archived
transcript.jsonl (result event modelUsage); score comes from grade.json.

    python import_baseline.py ~/Projects/rl-environments/tasks/<task>/runs/<run-dir> [...]
"""

import argparse
import json
from pathlib import Path

from harness.cc_driver import parse_transcript

RESULTS_DIR = Path(__file__).resolve().parent / "results"

MODEL_CONFIG = {"fable": "fable-solo", "opus": "opus-solo",
                "sonnet": "sonnet-solo", "haiku": "haiku-solo"}


def import_run(run_dir: Path) -> dict | None:
    meta = json.loads((run_dir / "meta.json").read_text())
    grade = json.loads((run_dir / "grade.json").read_text())
    transcript = run_dir / "transcript.jsonl"

    model_key = next((k for k in MODEL_CONFIG if k in meta.get("model", "")), None)
    if model_key is None:
        print(f"skip {run_dir.name}: unrecognized model {meta.get('model')!r}")
        return None
    label = f"{MODEL_CONFIG[model_key]}@cc"

    metrics = parse_transcript(transcript, sidekick_model=None)
    metrics.pop("lead_summary", None)
    error = metrics.pop("error", None)

    checkpoints = grade.get("checkpoints", {})
    result = {
        "task": meta["task"],
        "config": label,
        "driver": "cc",
        "imported_from": str(run_dir),
        "task_version": meta.get("task_version"),
        "lead_model": None,          # archived runs used CLI model aliases
        "sidekick_model": None,
        "score": {
            "score": grade["score"],
            "passed": sum(1 for ok in checkpoints.values() if ok),
            "total": len(checkpoints),
            "detail": f"imported grade.json (task v{grade.get('task_version', '?')})",
            "checkpoints": checkpoints,
        },
        "wall_seconds": meta.get("duration_seconds"),
        "error": error,
        "transcript": str(transcript),
        **metrics,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{meta['task']}__{label}__{run_dir.name}.json"
    if out.exists():
        print(f"skip {run_dir.name}: already imported ({out.name})")
        return None
    out.write_text(json.dumps(result, indent=2))
    print(f"imported {run_dir.name} -> {out.name}  "
          f"score={grade['score']} cost=${result['cost_usd']:.2f} "
          f"(cc reported ${result['cc_reported_cost_usd'] or 0:.2f}) "
          f"lead_turns={result['lead_turns']}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dirs", nargs="+", type=Path)
    args = parser.parse_args()
    for run_dir in args.run_dirs:
        if not (run_dir / "meta.json").exists():
            print(f"skip {run_dir}: no meta.json")
            continue
        import_run(run_dir.resolve())


if __name__ == "__main__":
    main()
