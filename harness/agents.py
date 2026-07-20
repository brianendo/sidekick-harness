"""Lead and sidekick agent loops.

The lead owns the session: reads the spec, plans, delegates via the `delegate`
tool (which runs a full sidekick loop in the same workspace), reviews, and
finishes. The sidekick receives a plain-language brief and works autonomously.
"""

import sys
from pathlib import Path

from .llm import call_model, served_by_fallback
from .metrics import Ledger
from .tools import DELEGATE_TOOL, FILE_TOOLS, ToolError, Workspace

MAX_LEAD_TURNS = 40
MAX_SIDEKICK_TURNS = 40

LEAD_SYSTEM = """You are the lead engineer on a coding task. You own this session end to end: read the spec, plan, get the work done, verify it, and finish only when the task is complete and verified.

Economics: your tokens are expensive. You have a sidekick engineer — a cheaper, capable model — available through the `delegate` tool. It works in the same workspace you see. Delegating implementation work is usually far cheaper than doing it yourself; it is your call when delegation fits the task.

When you delegate, write the brief like a spec: the goal, the constraints that must hold, and how success will be verified — not the exact code to type. Review the sidekick's work by inspecting the changed files or running the verification you specified. If something is wrong, prefer re-delegating a fix with a corrected brief over editing code yourself.

When the task is complete and verified, end your turn with a short summary of what was done and how it was verified."""

LEAD_SOLO_SYSTEM = """You are the engineer on a coding task. You own this session end to end: read the spec, plan, implement, verify, and finish only when the task is complete and verified.

When the task is complete and verified, end your turn with a short summary of what was done and how it was verified."""

SIDEKICK_SYSTEM = """You are an implementation engineer working in a shared workspace. You receive a brief from the lead engineer. Complete exactly what the brief asks: honor every stated constraint, verify your work (run the code or tests where possible), and do not expand scope beyond the brief.

Finish your turn with a concise report: what you changed, how you verified it, and anything the lead should double-check."""


def _cache_breakpoint(messages: list) -> None:
    """Keep exactly one incremental cache marker, on the newest user block.

    Only the dict messages we construct carry markers; assistant messages are
    SDK objects appended verbatim (which also preserves thinking blocks, as
    required for Fable multi-turn replay).
    """
    for msg in messages:
        if isinstance(msg, dict) and isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if isinstance(block, dict):
                    block.pop("cache_control", None)
    last = messages[-1]
    if isinstance(last, dict) and isinstance(last.get("content"), list):
        blocks = last["content"]
        if blocks and isinstance(blocks[-1], dict):
            blocks[-1]["cache_control"] = {"type": "ephemeral"}


class Session:
    def __init__(
        self,
        client,
        workspace: Workspace,
        ledger: Ledger,
        *,
        lead_model: str,
        sidekick_model: str | None,
        lead_effort: str = "high",
        sidekick_effort: str = "high",
        verbose: bool = True,
    ):
        self.client = client
        self.workspace = workspace
        self.ledger = ledger
        self.lead_model = lead_model
        self.sidekick_model = sidekick_model
        self.lead_effort = lead_effort
        self.sidekick_effort = sidekick_effort
        self.verbose = verbose
        # Full trajectory for post-hoc audit (e.g. oracle-hunting review):
        # one dict per assistant message / tool call / tool result.
        self.transcript: list[dict] = []

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg, file=sys.stderr, flush=True)

    # ------------------------------------------------------------------

    def run_lead(self, task_prompt: str) -> str:
        solo = self.sidekick_model is None
        system = LEAD_SOLO_SYSTEM if solo else LEAD_SYSTEM
        tools = FILE_TOOLS if solo else FILE_TOOLS + [DELEGATE_TOOL]
        first = (
            f"{task_prompt}\n\nWorkspace files:\n{self.workspace.list_files()}"
        )
        return self._agent_loop(
            role="lead",
            model=self.lead_model,
            system=system,
            tools=tools,
            first_message=first,
            effort=self.lead_effort,
            max_turns=MAX_LEAD_TURNS,
        )

    def run_sidekick(self, brief: str) -> str:
        before = self.workspace.snapshot()
        report = self._agent_loop(
            role="sidekick",
            model=self.sidekick_model,
            system=SIDEKICK_SYSTEM,
            tools=FILE_TOOLS,
            first_message=f"Brief from the lead engineer:\n\n{brief}",
            effort=self.sidekick_effort,
            max_turns=MAX_SIDEKICK_TURNS,
        )
        after = self.workspace.snapshot()
        changed = sorted(
            set(k for k in after if after.get(k) != before.get(k))
            | (set(before) - set(after))
        )
        changed_desc = "\n".join(changed) if changed else "(none)"
        return f"Sidekick report:\n{report}\n\nFiles changed by sidekick:\n{changed_desc}"

    # ------------------------------------------------------------------

    def _agent_loop(self, *, role, model, system, tools, first_message, effort, max_turns) -> str:
        messages: list = [
            {"role": "user", "content": [{"type": "text", "text": first_message}]}
        ]
        final_text = ""
        for turn in range(1, max_turns + 1):
            _cache_breakpoint(messages)
            response = call_model(
                self.client,
                model=model,
                system=system,
                tools=tools,
                messages=messages,
                effort=effort,
            )
            if role == "lead":
                self.ledger.lead_turns += 1
            else:
                self.ledger.sidekick_turns += 1
            self.ledger.record(role, response.model, response.usage)
            if served_by_fallback(response):
                self.ledger.fallbacks_served += 1

            if response.stop_reason == "refusal":
                self.ledger.refusals += 1
                self._log(f"  [{role}] refusal (stop_details={response.stop_details})")
                return "(request refused by safety classifiers)"

            texts = [b.text for b in response.content if b.type == "text" and b.text]
            if texts:
                final_text = "\n".join(texts)
                self.transcript.append(
                    {"role": role, "turn": turn, "type": "text",
                     "model": response.model, "text": final_text}
                )

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use" or not tool_uses:
                return final_text or "(no text output)"

            results = []
            for tu in tool_uses:
                results.append(self._run_tool(role, turn, tu))
            messages.append({"role": "user", "content": results})

        self._log(f"  [{role}] hit max_turns={max_turns}")
        return final_text + "\n(agent hit turn limit)"

    def _run_tool(self, role: str, turn: int, tu) -> dict:
        name, tool_input = tu.name, tu.input
        self._log(f"  [{role} t{turn}] {name} {str(tool_input)[:120]}")
        entry = {"role": role, "turn": turn, "type": "tool_use",
                 "name": name, "input": tool_input}
        self.transcript.append(entry)

        if name == "delegate":
            if role != "lead" or self.sidekick_model is None:
                result = _tool_result(tu.id, "delegate is not available here", is_error=True)
            else:
                self.ledger.delegations += 1
                if self.ledger.first_delegation_turn is None:
                    self.ledger.first_delegation_turn = turn
                try:
                    result = _tool_result(tu.id, self.run_sidekick(tool_input["brief"]))
                except Exception as e:  # sidekick loop failure shouldn't kill the lead
                    result = _tool_result(tu.id, f"Sidekick failed: {e}", is_error=True)
        else:
            if role == "lead" and name in ("write_file", "edit_file"):
                self.ledger.lead_code_edits += 1
            try:
                result = _tool_result(tu.id, self.workspace.dispatch(name, tool_input))
            except ToolError as e:
                result = _tool_result(tu.id, str(e), is_error=True)

        entry["result"] = result["content"]
        entry["is_error"] = result.get("is_error", False)
        return result


def _tool_result(tool_use_id: str, content: str, is_error: bool = False) -> dict:
    result = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        result["is_error"] = True
    return result
