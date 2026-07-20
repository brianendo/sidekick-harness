"""File and shell tools, sandboxed to a workspace directory."""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

BASH_TIMEOUT_S = 90
MAX_TOOL_OUTPUT = 10_000  # chars; long output is truncated head+tail

FILE_TOOLS = [
    {
        "name": "list_files",
        "description": "List files in the workspace (recursively).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "read_file",
        "description": "Read a file from the workspace. Path is relative to the workspace root.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": (
            "Replace an exact string in a file. old_str must appear exactly once."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_str": {"type": "string"},
                "new_str": {"type": "string"},
            },
            "required": ["path", "old_str", "new_str"],
        },
    },
    {
        "name": "run_bash",
        "description": (
            "Run a shell command with the workspace as the working directory. "
            "`python` / `python3` resolve to an interpreter with the project's "
            f"dependencies (incl. pytest) installed. Times out after {BASH_TIMEOUT_S}s."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
]

DELEGATE_TOOL = {
    "name": "delegate",
    "description": (
        "Hand a unit of work to your sidekick engineer — a cheaper model that works "
        "in the same workspace you see and reports back when done. Write the brief "
        "like a spec: the goal, the constraints that must hold, and how success will "
        "be verified. Do not dictate exact code. The result includes the sidekick's "
        "report and the list of files it changed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "brief": {
                "type": "string",
                "description": "Plain-language handoff brief for the sidekick.",
            }
        },
        "required": ["brief"],
    },
}


class ToolError(Exception):
    pass


def _truncate(text: str) -> str:
    if len(text) <= MAX_TOOL_OUTPUT:
        return text
    half = MAX_TOOL_OUTPUT // 2
    return text[:half] + f"\n... [{len(text) - MAX_TOOL_OUTPUT} chars truncated] ...\n" + text[-half:]


class Workspace:
    """A sandboxed directory the agents operate in."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _resolve(self, rel_path: str) -> Path:
        p = (self.root / rel_path).resolve()
        if not p.is_relative_to(self.root):
            raise ToolError(f"Path escapes workspace: {rel_path}")
        return p

    def snapshot(self) -> dict[str, str]:
        """Hash every file — used to report what the sidekick changed."""
        out = {}
        for p in sorted(self.root.rglob("*")):
            if p.is_file():
                out[str(p.relative_to(self.root))] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    # --- tool implementations -------------------------------------------

    def list_files(self) -> str:
        files = [str(p.relative_to(self.root)) for p in sorted(self.root.rglob("*")) if p.is_file()]
        return "\n".join(files) or "(empty workspace)"

    def read_file(self, path: str) -> str:
        p = self._resolve(path)
        if not p.is_file():
            raise ToolError(f"No such file: {path}")
        return _truncate(p.read_text())

    def write_file(self, path: str, content: str) -> str:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Wrote {len(content)} chars to {path}"

    def edit_file(self, path: str, old_str: str, new_str: str) -> str:
        p = self._resolve(path)
        if not p.is_file():
            raise ToolError(f"No such file: {path}")
        text = p.read_text()
        n = text.count(old_str)
        if n == 0:
            raise ToolError("old_str not found in file")
        if n > 1:
            raise ToolError(f"old_str appears {n} times; it must be unique")
        p.write_text(text.replace(old_str, new_str, 1))
        return f"Edited {path}"

    def run_bash(self, command: str) -> str:
        # Put the harness venv first on PATH so `python`/`python3`/`pytest`
        # inside the workspace resolve to an interpreter with task deps.
        env = os.environ.copy()
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=BASH_TIMEOUT_S,
                env=env,
            )
        except subprocess.TimeoutExpired:
            raise ToolError(f"Command timed out after {BASH_TIMEOUT_S}s")
        out = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
        return _truncate(f"[exit {proc.returncode}]\n{out.strip()}")

    def dispatch(self, name: str, tool_input: dict) -> str:
        """Run a file/shell tool. Raises ToolError for agent-visible errors."""
        handlers = {
            "list_files": lambda: self.list_files(),
            "read_file": lambda: self.read_file(tool_input["path"]),
            "write_file": lambda: self.write_file(tool_input["path"], tool_input["content"]),
            "edit_file": lambda: self.edit_file(
                tool_input["path"], tool_input["old_str"], tool_input["new_str"]
            ),
            "run_bash": lambda: self.run_bash(tool_input["command"]),
        }
        if name not in handlers:
            raise ToolError(f"Unknown tool: {name}")
        return handlers[name]()
