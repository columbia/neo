"""
Code-search primitives (paper §4.1).

One interface over the per-language CodeQL queries and the DuckDB call graph, so
an LLM agent can compose analyses without knowing any tool-specific syntax:

    Qname   name-based lookup        engine.qname(service, "update.*")
    Qast    AST-shaped lookup        engine.qast(service, "call" | "method")
    Qcg     call-graph traversal     engine.qcg(service, fn_id, "callers"|"callees")
    Qflow   intra-service flow       engine.qflow(service, "request", "update_role")
    Qsource data sources             engine.qsource(service)
    Qinter  inter-service calls      engine.qinter(service)
    Qglobalflow cross-service graph  engine.qglobalflow()

    property fns: get_location(el), get_source(service, el), get_type(service, el)

Fidelity notes
--------------
* Qname / Qast("call"|"method") / Qcg run against the DuckDB call graph — exact.
* Qast also answers field_access/assignment/return/string_literal/conditional/
  catch/parameter/new via a generated CodeQL query (``astSearch.ql``) — all 6
  languages; falls back to ``{"unsupported": ...}`` only if no template exists.
* Qflow answers from the flows already computed by ``--find-flows`` /
  ``--global-flows`` by default (fast, approximate); passing
  ``{"precise": true}`` (or ``NEO_QFLOW_PRECISE=1``) issues a fresh on-demand
  taint query naming source/sink directly instead (``templateFlowFromTo.ql``).
* get_type reads the recorded signature; returns ``"unknown"`` when absent —
  no real type inference.
* bash() is the fallback when none of the above can name what the agent is
  looking for: a sandboxed, allowlisted, read-only shell scoped to the
  service's source tree (grep/find/ls/cat/... — no writes, no network, no
  path outside the sandbox). See its docstring for the exact guarantees.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from common.services import Application, Service, load_application
from duck_db.create_duckdb import CallGraphDatabase


def _as_app(app_or_name) -> Application:
    if isinstance(app_or_name, Application):
        return app_or_name
    if isinstance(app_or_name, Service):
        return Application(name=app_or_name.name, services=[app_or_name])
    return load_application(str(app_or_name))


class Unsupported(dict):
    """A primitive result meaning 'not available for this language/target'."""


class CodeSearchEngine:
    def __init__(self, app_or_name):
        self.app = _as_app(app_or_name)
        self._db: Dict[str, Optional[CallGraphDatabase]] = {}

    # -- infra -----------------------------------------------------------
    def _service(self, name: Optional[str]) -> Service:
        if name is None:
            return self.app.services[0]
        svc = self.app.get(name)
        if svc is None:
            raise KeyError(f"no service named {name!r} (have: {[s.name for s in self.app.services]})")
        return svc

    def _get_db(self, name: Optional[str]) -> Optional[CallGraphDatabase]:
        svc = self._service(name)
        if svc.name not in self._db:
            p = svc.duckdb_path
            self._db[svc.name] = CallGraphDatabase(p) if p.exists() else None
        return self._db[svc.name]

    @staticmethod
    def _fn_element(row: Dict, service: str) -> Dict:
        return {
            "kind": "function",
            "id": row.get("function_id") or f"{row.get('name')}@{row.get('file_path')}:{row.get('start_line')}",
            "name": row.get("name"),
            "file": row.get("file_path"),
            "line": row.get("start_line"),
            "end_line": row.get("end_line"),
            "class_name": row.get("class_name"),
            "signature": row.get("signature"),
            "service": service,
        }

    def close(self):
        for db in self._db.values():
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

    # -- primitives ----------------------------------------------------
    def qname(self, service: Optional[str], name: str,
              kinds=("function", "class"), limit: int = 200) -> List[Dict]:
        db = self._get_db(service)
        if db is None:
            return []
        sname = self._service(service).name
        out: List[Dict] = []
        if "function" in kinds:
            out += [self._fn_element(r, sname) for r in db.search_functions_by_name(name, limit)]
        if "class" in kinds:
            for r in db.search_classes_by_name(name, limit):
                out.append({
                    "kind": "class", "id": r.get("class_id"), "name": r.get("name"),
                    "file": r.get("file_path"), "line": r.get("start_line"),
                    "end_line": r.get("end_line"), "service": sname,
                })
        return out

    def qast(self, service: Optional[str], operation: str, limit: int = 2000):
        op = operation.strip().lower()
        svc = self._service(service)
        sname = svc.name
        db = self._get_db(service)

        # fast DuckDB-backed paths
        if op in ("method", "function", "callable"):
            return [] if db is None else [self._fn_element(r, sname) for r in db.all_functions(limit)]
        if op in ("call", "callsite", "invocation") and db is not None:
            cur = db.conn.execute("SELECT callsite_id, target_function_id FROM call_resolutions LIMIT ?", [limit])
            res = []
            for callsite_id, target in cur.fetchall():
                loc = callsite_id.rsplit("@", 1)[-1] if "@" in callsite_id else ""
                f, _, ln = loc.rpartition(":")
                res.append({
                    "kind": "call", "id": callsite_id, "name": callsite_id.split("@")[0],
                    "file": f, "line": int(ln) if ln.isdigit() else 0,
                    "target": target, "service": sname,
                })
            return res

        # richer ops via a generated CodeQL query (Java / Python)
        rows = self._qast_codeql(svc, op, limit)
        if rows is not None:
            return rows
        return Unsupported(
            unsupported=f"Qast operation {operation!r} for language "
            f"{svc._safe_language() or '?'}",
            supported=sorted({"call", "method", "field_access", "assignment", "return",
                              "string_literal", "conditional", "catch", "parameter", "new"}),
        )

    def _qast_codeql(self, svc: Service, op: str, limit: int) -> Optional[List[Dict]]:
        lang = (svc._safe_language() or "").lower()
        db_dir = Path(svc.database_dir)
        if lang not in ("java", "python", "go", "javascript", "csharp", "cpp") or not db_dir.exists() or not os.getenv("CODEQL_BIN"):
            return None
        try:
            from common.codeql import execute_query
            from common.sarif_parser import stream_sarif_results
            from genquery.gen_astsearch import gen_astsearch_query, normalize_op
        except Exception:
            return None
        if normalize_op(op) is None:
            return None
        q = gen_astsearch_query(lang, svc.key, op)
        if q is None:
            return None
        sarif = svc.workdir / f"qast_{q.stem}.sarif"
        ok = execute_query(query_path=q, database_path=db_dir, output_file=sarif,
                           query_wd=q.parent.parent, rerun=False)
        if not ok or not sarif.exists():
            return None
        out: List[Dict] = []
        for res in stream_sarif_results(sarif):
            msg = (res.get("message", {}) or {}).get("text", "")
            if not msg.startswith("AST|"):
                continue
            parts = msg.split("|", 3)
            if len(parts) < 4:
                continue
            _tag, kind, label, floc = parts
            f, _, ln = floc.rpartition(":")
            out.append({"kind": kind, "name": label.strip()[:120], "file": f,
                        "line": int(ln) if ln.strip().isdigit() else 0,
                        "id": f"{label.strip()[:40]}@{floc}", "service": svc.name})
            if len(out) >= limit:
                break
        return out

    def qcg(self, service: Optional[str], function: str, direction: str = "callers") -> List[Dict]:
        db = self._get_db(service)
        if db is None:
            return []
        sname = self._service(service).name
        d = direction.strip().lower()
        # accept a name or a full id
        fid = function
        if "@" not in function:
            hits = db.search_functions_by_name(f"^{re.escape(function)}$", limit=1) or db.get_functions_by_name(function)
            if not hits:
                return []
            fid = hits[0].get("function_id") or fid
        rows = db.get_callers(fid) if d.startswith("caller") else db.get_callees(fid)
        return [self._fn_element(r, sname) | {"callsite": r.get("callsite")} for r in rows]

    def qflow(self, service: Optional[str], source: str, sink: str,
              precise: Optional[bool] = None) -> List[Dict]:
        """
        Does taint flow from something matching *source* to something matching
        *sink* in this service?

        Default (fast): match against flows already computed by --find-flows /
        --global-flows.  With ``precise`` (or ``NEO_QFLOW_PRECISE=1``) and a
        Java/Python database present, issue a real on-demand CodeQL taint query.
        """
        if precise is None:
            precise = os.getenv("NEO_QFLOW_PRECISE", "0") == "1"
        if precise:
            real = self._qflow_codeql(service, source, sink)
            if real is not None:
                return real
        return self._qflow_approx(service, source, sink)

    def _qflow_codeql(self, service, source, sink) -> Optional[List[Dict]]:
        svc = self._service(service)
        lang = (svc._safe_language() or "").lower()
        db_dir = Path(svc.database_dir)
        if lang not in ("java", "python", "go", "javascript", "csharp", "cpp") or not db_dir.exists() or not os.getenv("CODEQL_BIN"):
            return None
        try:
            from common.codeql import execute_query
            from common.sarif_parser import extract_sarif_location, stream_sarif_results
            from genquery.gen_flowfromto import gen_flowfromto_query
        except Exception:
            return None

        q = gen_flowfromto_query(lang, svc.key, source, sink)
        if q is None:
            return None
        sarif = svc.workdir / f"qflow_{q.stem}.sarif"
        ok = execute_query(query_path=q, database_path=db_dir, output_file=sarif,
                           query_wd=q.parent.parent, rerun=False)
        if not ok or not sarif.exists():
            return None
        flows: List[Dict] = []
        for res in stream_sarif_results(sarif):
            locs = res.get("locations") or []
            rel = res.get("relatedLocations") or []
            if not locs:
                continue
            sink_loc = extract_sarif_location(locs[0])
            src_loc = extract_sarif_location(rel[0]) if rel else sink_loc
            flows.append({
                "kind": "flow", "service": svc.name, "approximate": False,
                "source_location": f"{src_loc['file']}:{src_loc['start_line']}",
                "sink_location": f"{sink_loc['file']}:{sink_loc['start_line']}",
                "query": str(q),
            })
        return flows

    def _qflow_approx(self, service: Optional[str], source: str, sink: str) -> List[Dict]:
        """Approximate: match against flows already computed for this service."""
        svc = self._service(service)
        wd = svc.workdir
        matched: List[Dict] = []
        for fname in ("FlowSourceSink.json", "Flow2Out.json"):
            data = _load_json(wd / fname)
            for _grp, flows in (data.get("grouped_flows") or {}).items():
                for flow in flows:
                    steps = flow.get("steps") or []
                    if not steps:
                        continue
                    blob_first = f"{steps[0].get('statement','')} {steps[0].get('function_id','')} {flow.get('source_location','')}"
                    blob_last = f"{steps[-1].get('statement','')} {steps[-1].get('function_id','')} {flow.get('sink_location','')}"
                    if _loose(source) in blob_first.lower() and _loose(sink) in blob_last.lower():
                        matched.append({
                            "kind": "flow", "service": svc.name,
                            "source_location": flow.get("source_location"),
                            "sink_location": flow.get("sink_location"),
                            "steps": steps, "approximate": True,
                        })
        return matched

    def qsource(self, service: Optional[str]) -> List[Dict]:
        svc = self._service(service)
        wd = svc.workdir
        out: List[Dict] = []
        s2s = _load_json(wd / "FlowSourceSink.json")
        seen = set()
        for _g, flows in (s2s.get("grouped_flows") or {}).items():
            for flow in flows:
                loc = flow.get("source_location", "")
                if loc and loc not in seen:
                    seen.add(loc)
                    out.append({"kind": "source", "location": loc, "service": svc.name,
                                "file": loc.split(":")[0]})
        for ep in (_load_json(wd / "endpoints.json").get("endpoints") or []):
            out.append({"kind": "source", "role": "endpoint", "service": svc.name,
                        "route": ep.get("route"), "method": ep.get("method"),
                        "handler": ep.get("handler"), "file": ep.get("file"),
                        "line": ep.get("line")})
        return out

    def qinter(self, service: Optional[str]) -> List[Dict]:
        svc = self._service(service)
        data = _load_json(svc.workdir / "interservice.json")
        return list(data.get("outbound_calls") or [])

    def qglobalflow(self) -> Dict:
        from interlang.graph import build_graph
        from interlang.stitch import stitch
        g = build_graph(self.app)
        return stitch(self.app, g)

    # -- property functions -----------------------------------------
    def get_location(self, element: Dict) -> Dict:
        loc = element.get("location") or (
            f"{element.get('file')}:{element.get('line')}" if element.get("file") else element.get("id", "")
        )
        return {"service": element.get("service"), "location": loc,
                "file": element.get("file"), "line": element.get("line")}

    def get_source(self, service: Optional[str], element: Dict, context: int = 12) -> Optional[str]:
        """
        Source for a returned element — a whole function/class body, or a
        ``context``-line window around a plain ``file:line`` element (call site,
        source, endpoint).  ``element`` may also be ``{"file": ..., "line": ...}``.
        """
        svc = self._service(service)
        root = Path(svc.source_dir)
        ident = element.get("id") if isinstance(element, dict) else str(element)

        db = self._get_db(service)
        if db is not None and ident and "@" in str(ident):
            infos = db.get_function_by_identifier(str(ident), source_root=root)
            if infos:
                code = db.get_function_source_code(infos[0], root)
                if code:
                    return code

        # fall back to a line window from the file
        file = (element.get("file") or "").strip() if isinstance(element, dict) else ""
        line = element.get("line") if isinstance(element, dict) else None
        if not file and ident and "@" in str(ident):
            loc = str(ident).split("@", 1)[1]
            file, _, ln = loc.rpartition(":")
            line = int(ln) if ln.isdigit() else line
        if not file or not line:
            return None
        end_line = element.get("end_line") if isinstance(element, dict) else None
        return _read_window(root / file, int(line),
                            int(end_line) if end_line else None, context)

    def get_type(self, service: Optional[str], element: Dict) -> str:
        if isinstance(element, dict) and element.get("signature"):
            return str(element["signature"])
        db = self._get_db(service)
        if db is not None and isinstance(element, dict) and element.get("id"):
            info = db.get_function_definition(element["id"])
            if info and info.get("signature"):
                return info["signature"]
        return "unknown"

    # -- fallback tool -------------------------------------------------
    def bash(self, service: Optional[str], command: str) -> Dict:
        """
        Read-only shell fallback for when qname/qast/qflow don't surface what
        the agent is looking for (e.g. a string or pattern that isn't a
        function/AST-node name: a config value, a comment, a route defined by
        string concatenation the CodeQL queries didn't model). Sandboxed to
        the service's source tree via an allowlist of read-only commands --
        not merely discouragement, enforced: no redirection, substitution,
        backgrounding, absolute/parent-relative paths, or the handful of
        allowlisted binaries' own "run anything" flags (find -exec, sed -i).
        Runs with cwd pinned to the service root and a minimal environment.
        """
        if os.getenv("NEO_AGENT_BASH", "1") == "0":
            return {"error": "bash fallback is disabled (NEO_AGENT_BASH=0)"}
        svc = self._service(service)
        root = Path(svc.source_dir).resolve()
        reason = _bash_command_rejection(command)
        if reason:
            return {"error": f"command rejected: {reason}"}
        try:
            proc = subprocess.run(
                ["bash", "-c", command],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=_BASH_TIMEOUT_S,
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"},
            )
        except subprocess.TimeoutExpired:
            return {"error": f"command timed out after {_BASH_TIMEOUT_S}s"}
        except OSError as e:
            return {"error": f"could not run command: {e}"}
        return {
            "exit_code": proc.returncode,
            "stdout": _clip(proc.stdout),
            "stderr": _clip(proc.stderr),
            "cwd": f"services/{svc.name}",
        }


# ---------------------------------------------------------------------------

def _load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}


def _read_window(path: Path, line: int, end_line: Optional[int], context: int) -> Optional[str]:
    """Numbered source lines around [line, end_line] (or ±context)."""
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return None
    lo = max(1, line - context)
    hi = min(len(lines), (end_line or line) + context)
    if lo > len(lines):
        return None
    return "\n".join(f"{n}:{lines[n - 1]}" for n in range(lo, hi + 1))


def _loose(s: str) -> str:
    return (s or "").strip().lower().strip("\"'")


# ---------------------------------------------------------------------------
# bash() sandboxing — an allowlist, not a denylist: every binary the fallback
# tool may invoke is read-only by construction, and the handful with a "run
# something else" escape hatch (find -exec, sed -i) have that flag blocked.
# xargs and awk are excluded entirely: xargs' whole purpose is invoking an
# arbitrary trailing command (bypassing the allowlist), and awk's system()
# runs an arbitrary shell command from inside a quoted script string, where a
# token-level check can't see it.
# ---------------------------------------------------------------------------
_BASH_TIMEOUT_S = 15
_BASH_MAX_OUTPUT = 8000
_BASH_ALLOWED_BINS = {
    "grep", "egrep", "fgrep", "rg", "ag", "find", "ls", "cat", "head", "tail",
    "wc", "sed", "cut", "sort", "uniq", "tree", "file", "basename", "dirname",
    "echo", "pwd", "strings",
}
_BASH_FORBIDDEN_FLAGS = {
    "find": {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint",
              "-fprint0", "-fprintf"},
    "sed": {"-i", "--in-place"},
}
_BASH_METACHAR_RE = re.compile(r"\$\(|`|>>|>|<\(|&")


def _bash_command_rejection(command: str) -> Optional[str]:
    """``None`` if *command* is safe to run sandboxed to the service root;
    otherwise a human-readable reason it was rejected."""
    if not command or not command.strip():
        return "empty command"
    if _BASH_METACHAR_RE.search(command):
        return "redirection, command substitution, and backgrounding are not allowed"
    for segment in re.split(r"\|\||&&|\||;", command):
        segment = segment.strip()
        if not segment:
            continue
        try:
            tokens = shlex.split(segment)
        except ValueError as e:
            return f"could not parse command: {e}"
        if not tokens:
            continue
        bin_name = Path(tokens[0]).name
        if bin_name not in _BASH_ALLOWED_BINS:
            return f"'{bin_name}' is not in the read-only allowlist {sorted(_BASH_ALLOWED_BINS)}"
        forbidden = _BASH_FORBIDDEN_FLAGS.get(bin_name)
        if forbidden and forbidden & set(tokens):
            return f"'{bin_name}' may not be used with {sorted(forbidden & set(tokens))}"
        for tok in tokens[1:]:
            if tok.startswith("/") or tok.startswith("~") or ".." in Path(tok).parts:
                return f"argument '{tok}' escapes the service's source tree"
    return None


def _clip(s: str) -> str:
    s = s or ""
    return s if len(s) <= _BASH_MAX_OUTPUT else s[:_BASH_MAX_OUTPUT] + "\n... (truncated)"
