"""Task loading and scoring for two task sources:

1. Local tasks (tasks/<name>/):
     workspace/  — files the agents see (spec.md + starters)
     tests/      — hidden pytest suite, copied in only at scoring time
   Score = fraction of hidden tests passed.

2. rl-environments tasks (external, discovered from $RLENV_TASKS_DIR or
   ~/Projects/rl-environments/tasks). Anatomy per that repo:
     task.md   — symptoms-only ticket (used verbatim as the prompt)
     world/    — the scrubbed workspace agents see
     grade.py  — self-contained weighted-checkpoint grader
                 (`--solution <dir> --out grade.json`)
   Score = grade.py's weighted checkpoint score.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"
GRADE_TIMEOUT_S = 1200


@dataclass
class Task:
    name: str
    kind: str  # "local" | "rlenv"
    path: Path
    prompt: str


# --- discovery ---------------------------------------------------------


def rlenv_tasks_dir() -> Path | None:
    env = os.environ.get("RLENV_TASKS_DIR")
    if env:
        p = Path(env).expanduser()
        return p if p.is_dir() else None
    default = Path.home() / "Projects" / "rl-environments" / "tasks"
    return default if default.is_dir() else None


def _is_rlenv_task(p: Path) -> bool:
    return (p / "task.md").is_file() and (p / "world").is_dir() and (p / "grade.py").is_file()


def list_tasks() -> list[str]:
    names = sorted(p.name for p in TASKS_DIR.iterdir() if (p / "task.json").exists())
    rlenv = rlenv_tasks_dir()
    if rlenv:
        names += sorted(p.name for p in rlenv.iterdir() if p.is_dir() and _is_rlenv_task(p))
    return names


def load_task(name: str) -> Task:
    local = TASKS_DIR / name
    if (local / "task.json").exists():
        meta = json.loads((local / "task.json").read_text())
        spec = (local / "workspace" / "spec.md").read_text()
        prompt = f"{meta['prompt']}\n\n--- spec.md ---\n{spec}"
        return Task(name=name, kind="local", path=local, prompt=prompt)

    rlenv = rlenv_tasks_dir()
    if rlenv and _is_rlenv_task(rlenv / name):
        path = rlenv / name
        # task.md verbatim — the ticket is the whole spec, behavioral voice.
        return Task(name=name, kind="rlenv", path=path, prompt=(path / "task.md").read_text())

    raise FileNotFoundError(f"Unknown task: {name} (looked in {TASKS_DIR} and {rlenv})")


# --- workspace ---------------------------------------------------------


def make_run_workspace(task: Task) -> Path:
    """Copy the task's agent-visible files into a fresh temp directory."""
    run_dir = Path(tempfile.mkdtemp(prefix=f"sidekick-{task.name}-"))
    src = task.path / ("workspace" if task.kind == "local" else "world")
    shutil.copytree(
        src,
        run_dir,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".venv"),
    )
    return run_dir


# --- scoring -----------------------------------------------------------


def score_workspace(task: Task, workspace_root: Path) -> dict:
    if task.kind == "rlenv":
        return _score_rlenv(task, workspace_root)
    return _score_local(task, workspace_root)


def _score_rlenv(task: Task, workspace_root: Path) -> dict:
    """Run the task's own grade.py against the finished workspace."""
    with tempfile.TemporaryDirectory(prefix="grade-out-") as tmp:
        out = Path(tmp) / "grade.json"
        try:
            proc = subprocess.run(
                [sys.executable, str(task.path / "grade.py"),
                 "--solution", str(workspace_root), "--out", str(out)],
                capture_output=True,
                text=True,
                timeout=GRADE_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            return {"score": 0.0, "passed": 0, "total": 0, "detail": "grade.py timed out"}
        if not out.exists():
            tail = (proc.stdout + proc.stderr).strip().splitlines()
            return {"score": 0.0, "passed": 0, "total": 0,
                    "detail": f"grade.py failed (exit {proc.returncode}): "
                              + (tail[-1] if tail else "no output")}
        report = json.loads(out.read_text())

    checkpoints = report.get("checkpoints", {})
    return {
        "score": report["score"],
        "passed": sum(1 for ok in checkpoints.values() if ok),
        "total": len(checkpoints),
        "detail": f"weighted checkpoints (task v{report.get('task_version', '?')})",
        "checkpoints": checkpoints,
        "modified_guarded_files": report.get("modified_guarded_files", []),
        # full grader report fields (pass/blockers on newer tasks, per-checkpoint
        # output tails) — kept so failed checkpoints are debuggable post-hoc
        "blockers": report.get("blockers"),
        "grader_pass": report.get("pass"),
        "tails": report.get("tails"),
    }


def _score_local(task: Task, workspace_root: Path, timeout_s: int = 120) -> dict:
    """Copy hidden tests into the finished workspace and run pytest."""
    tests_dst = workspace_root / ".hidden_tests"
    if tests_dst.exists():
        shutil.rmtree(tests_dst)
    shutil.copytree(task.path / "tests", tests_dst)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dst), "-q", "--tb=no",
             "-p", "no:cacheprovider"],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        output = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return {"score": 0.0, "passed": 0, "total": _count_tests(task), "detail": "pytest timed out"}

    passed = _extract(r"(\d+) passed", output)
    failed = _extract(r"(\d+) failed", output)
    errors = _extract(r"(\d+) error", output)
    total = passed + failed + errors
    if total == 0:
        # collection failure (module missing / import error) — everything fails
        return {"score": 0.0, "passed": 0, "total": _count_tests(task),
                "detail": output.strip().splitlines()[-1] if output.strip() else "no tests ran"}
    return {"score": round(passed / total, 4), "passed": passed, "total": total,
            "detail": output.strip().splitlines()[-1]}


def _extract(pattern: str, text: str) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0


def _count_tests(task: Task) -> int:
    n = 0
    for f in (task.path / "tests").glob("test_*.py"):
        n += len(re.findall(r"^def test_", f.read_text(), re.MULTILINE))
    return n
