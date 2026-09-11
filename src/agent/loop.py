"""
Perception-action loop (paper §5 "Agent Orchestration").

The LLM is given the task, the tool surface (the code-search primitives) and the
running transcript; each turn it emits one or more ``<action>`` blocks and/or a
``<final>`` block.  The loop executes the actions against
:class:`agent.primitives.CodeSearchEngine`, appends the observations and
re-prompts, stopping on ``<final>``, on a turn with no actions, or at
``max_iterations``.

Action syntax (either form works):

    <action name="qname">{"service": "user-mgmt", "name": "update.*"}</action>
    <action name="get_source">{"service": "user-mgmt", "element": {"id": "update_role@app/main.py:30"}}</action>
    <final>{"privileged_operations": [ ... ]}</final>
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_ACTION_RE = re.compile(r"<action\s+name=\"([a-zA-Z_]+)\"\s*>(.*?)</action>", re.DOTALL)
_FINAL_RE = re.compile(r"<final>(.*?)</final>", re.DOTALL)

# how much of each observation to feed back (protects the context window)
_MAX_ITEMS = 40
_MAX_CHARS = 6000


class AgentLoop:
    def __init__(self, llm, engine, *, max_iterations: int = 12,
                 logdir: Optional[Path] = None, extra_tools: Optional[Dict[str, Callable]] = None):
        self.llm = llm
        self.engine = engine
        self.max_iterations = max_iterations
        self.logdir = Path(logdir) if logdir else None
        if self.logdir:
            self.logdir.mkdir(parents=True, exist_ok=True)
        self.transcript: List[Dict[str, str]] = []
        self._tools = self._build_tools()
        if extra_tools:
            self._tools.update(extra_tools)

    # -- tool table ----------------------------------------------------
    def _build_tools(self) -> Dict[str, Callable[[dict], Any]]:
        e = self.engine
        return {
            "qname": lambda a: e.qname(a.get("service"), a["name"],
                                       tuple(a.get("kinds", ("function", "class"))),
                                       int(a.get("limit", 200))),
            "qast": lambda a: e.qast(a.get("service"), a["operation"], int(a.get("limit", 2000))),
            "qcg": lambda a: e.qcg(a.get("service"), a["function"], a.get("direction", "callers")),
            "qflow": lambda a: e.qflow(a.get("service"), a["source"], a["sink"], a.get("precise")),
            "qsource": lambda a: e.qsource(a.get("service")),
            "qinter": lambda a: e.qinter(a.get("service")),
            "qglobalflow": lambda a: e.qglobalflow(),
            "get_location": lambda a: e.get_location(a["element"]),
            "get_source": lambda a: e.get_source(a.get("service"), a["element"]),
            "get_type": lambda a: e.get_type(a.get("service"), a["element"]),
            "bash": lambda a: e.bash(a.get("service"), a["command"]),
        }

    def tool_names(self) -> List[str]:
        return sorted(self._tools)

    # -- run ---------------------------------------------------------
    def run(self, task_prompt: str) -> Dict[str, Any]:
        history: List[Dict[str, str]] = []
        message = [{"role": "user", "content": task_prompt}]
        final: Optional[Any] = None
        iterations = 0

        for iterations in range(1, self.max_iterations + 1):
            resp = self.llm.messages_create(history=history, message=message,
                                            max_tokens=4000, temperature=0.1)
            text = resp.content[0].text
            history += message
            history.append({"role": "assistant", "content": text})
            self._log(iterations, "assistant", text)

            fin = _FINAL_RE.search(text)
            if fin:
                final = _parse_json(fin.group(1))
                break

            actions = _ACTION_RE.findall(text)
            if not actions:
                # no actions and no <final> — nudge once, then stop
                message = [{"role": "user", "content":
                            "No <action> or <final> block found. Emit one <action name=\"...\">{json}</action> "
                            "per tool call, or <final>{json}</final> when done."}]
                if iterations >= 2:
                    break
                continue

            observations = []
            for name, raw_args in actions:
                obs = self._dispatch(name, raw_args)
                observations.append(f'<observation for="{name}">\n{obs}\n</observation>')
            obs_text = "\n\n".join(observations)
            self._log(iterations, "observation", obs_text)
            message = [{"role": "user", "content": obs_text}]

        return {
            "final": final,
            "iterations": iterations,
            "stopped": "final" if final is not None else "max_iterations",
            "transcript": self.transcript,
        }

    # -- dispatch --------------------------------------------------
    def _dispatch(self, name: str, raw_args: str) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"error": f"unknown tool {name!r}", "available": self.tool_names()})
        try:
            args = _parse_json(raw_args) or {}
            if not isinstance(args, dict):
                return json.dumps({"error": "action body must be a JSON object"})
            result = tool(args)
        except KeyError as e:
            return json.dumps({"error": f"missing required arg {e}"})
        except Exception as e:  # keep the loop alive on a bad call
            return json.dumps({"error": f"{type(e).__name__}: {e}"})
        return _render_result(result)

    # -- logging -------------------------------------------------
    def _log(self, i: int, role: str, content: str):
        self.transcript.append({"iteration": i, "role": role, "content": content})
        if self.logdir:
            (self.logdir / f"{i:02d}_{role}.txt").write_text(content)


def _parse_json(s: str) -> Any:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # tolerate a trailing ``` fence or prose around the object
        m = re.search(r"\{.*\}|\[.*\]", s, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
        return None


def _render_result(result: Any) -> str:
    if isinstance(result, list):
        clipped = result[:_MAX_ITEMS]
        note = "" if len(result) <= _MAX_ITEMS else f"\n... ({len(result) - _MAX_ITEMS} more truncated)"
        body = json.dumps(clipped, indent=2, default=str)
        return (body[:_MAX_CHARS] + note) if len(body) <= _MAX_CHARS else body[:_MAX_CHARS] + "\n... (truncated)"
    body = json.dumps(result, indent=2, default=str) if not isinstance(result, str) else result
    return body[:_MAX_CHARS] + ("\n... (truncated)" if len(body) > _MAX_CHARS else "")
