"""
Agent-driven privileged-operation discovery (paper §4.2, Step 1).

This is the paper-faithful alternative to the one-shot regex in
``sinks.find_sinks.get_customize_op``: an LLM composes the code-search
primitives, validates each candidate against its source, and iterates.

    python main.py --app <app> --agent            # discover -> agent_privileged_ops.json
    python main.py --app <app> --agent --find-sinks --find-flows --validate-flows

The result is written to each service's ``neo-workdir/agent_privileged_ops.json``
and merged into the customized-sink CodeQL query, so the rest of the pipeline
(``--find-flows`` / ``--validate-flows``) picks it up unchanged.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from common.helper import get_app_description, get_prompt_dir
from common.services import Application, load_application

from .loop import AgentLoop
from .primitives import CodeSearchEngine


def _task_prompt(app: Application) -> str:
    tools = (get_prompt_dir() / "agent_tools.md").read_text()
    task = (get_prompt_dir() / "agent_task.md").read_text()
    desc = get_app_description(app.name) or "(no README found)"
    multi = "polyglot micro" if app.is_multi_service else ""
    services = ", ".join(f"{s.name} [{s._safe_language() or '?'}]" for s in app.services)
    body = (task
            .replace("%%MULTISERVICE%%", (multi + " " if multi else ""))
            .replace("%%DESCRIPTION%%", desc)
            .replace("%%SERVICES%%", services))
    return tools + "\n\n---\n\n" + body


def agent_find_privileged_ops(appname: str, llm_client, max_iterations: Optional[int] = None) -> Dict:
    app = load_application(appname)
    engine = CodeSearchEngine(app)

    max_iterations = max_iterations or int(os.getenv("AGENT_MAX_ITERATIONS", "12"))
    logdir = _first_workdir(app) / "agent_logs" / "find_privileged_ops"
    loop = AgentLoop(llm_client, engine, max_iterations=max_iterations, logdir=logdir)

    print(f"[agent] discovering privileged operations in '{app.name}' "
          f"(services: {', '.join(s.name for s in app.services)}, max_iter={max_iterations})")
    result = loop.run(_task_prompt(app))
    engine.close()

    ops: List[Dict] = []
    final = result.get("final") or {}
    if isinstance(final, dict):
        ops = final.get("privileged_operations") or []
    elif isinstance(final, list):
        ops = final

    _write_per_service(app, ops, result)
    print(f"[agent] {len(ops)} privileged operations after {result['iterations']} iterations "
          f"(stopped: {result['stopped']})")
    return {"privileged_operations": ops, "iterations": result["iterations"],
            "stopped": result["stopped"]}


def _first_workdir(app: Application) -> Path:
    wd = app.services[0].workdir
    wd.mkdir(parents=True, exist_ok=True)
    return wd


def _write_per_service(app: Application, ops: List[Dict], run_result: Dict) -> None:
    by_service: Dict[str, List[Dict]] = {s.name: [] for s in app.services}
    default = app.services[0].name
    for op in ops:
        by_service.setdefault(op.get("service") or default, []).append(op)

    for svc in app.services:
        svc.workdir.mkdir(parents=True, exist_ok=True)
        out = {
            "service": svc.name,
            "application": app.name,
            "iterations": run_result.get("iterations"),
            "stopped": run_result.get("stopped"),
            "privileged_operations": by_service.get(svc.name, []),
        }
        (svc.workdir / "agent_privileged_ops.json").write_text(json.dumps(out, indent=2))


def merge_into_customize_op(appname: str) -> int:
    """
    Feed the agent's privileged operations into the customized-sink CodeQL query
    (same hook ``sinks.find_sinks`` uses for LLM-proposed sinks).
    """
    from common.helper import AnalysisStatus, update_status, get_database_language, get_app_database_dir
    from genquery.gen_callsite import gen_callsite_query

    app = load_application(appname)
    total = 0
    for svc in app.services:
        f = svc.workdir / "agent_privileged_ops.json"
        if not f.exists():
            continue
        ops = json.loads(f.read_text()).get("privileged_operations") or []
        names = sorted({op["name"] for op in ops if op.get("name")})
        if not names:
            continue
        # exact-name regexes for the callsite query
        patterns = [f"^{_escape(n)}$" for n in names]
        try:
            language = get_database_language(get_app_database_dir(svc.key))
        except Exception:
            language = svc._safe_language()
        if not language:
            continue
        gen_callsite_query(patterns, language, svc.key)
        update_status(svc.key, AnalysisStatus.WRITE_CUSTOMEOP)
        total += len(names)
        print(f"[agent] merged {len(names)} sink name(s) into {svc.key} customized-sink query")
    return total


def _escape(name: str) -> str:
    return "".join("\\" + c if c in r".^$*+?()[]{}|\\" else c for c in name)
