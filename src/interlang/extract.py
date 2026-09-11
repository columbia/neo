"""
Per-service extraction of inter-service communication points (``Qinter``).

Two artifacts are produced per service, under its ``neo-workdir``:

* ``interservice.json`` — outbound calls + channel identifiers
* ``endpoints.json``    — inbound endpoints (routes / consumers) + handlers

Preferred source is CodeQL (``queries/<lang>/interservice.ql`` /
``endpoints.ql``); when those are absent or produce nothing we fall back to
cheap heuristics over the already-computed ``Flow2Out.json`` and a regex scan
of the service source tree, so the cross-service engine is usable before the
language-specific queries are fully built out.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from common.helper import get_endpoints_query, get_interservice_query
from common.sarif_parser import extract_sarif_location, stream_sarif_results

F_OUT = "Flow2Out.json"
INTERSERVICE_JSON = "interservice.json"
INTERSERVICE_SARIF = "interservice.sarif"
ENDPOINTS_JSON = "endpoints.json"
ENDPOINTS_SARIF = "endpoints.sarif"

try:  # optional: only needed when actually invoking CodeQL
    from common.codeql import execute_query
except Exception:  # pragma: no cover
    execute_query = None

_VENDOR = re.compile(
    r"(^|/)(node_modules|site-packages|dist-packages|vendor|third_party|\.venv|venv|"
    r"target/generated-sources|build|__pycache__|testdata|test/|tests/)(/|$)"
)

_URL_RE = re.compile(r"""https?://[^\s"'`)]+""")
_STR_RE = re.compile(r"""["'`](/[A-Za-z0-9_./:{}<>*\-]*)["'`]""")
_TOPIC_RE = re.compile(r"""["'`]([A-Za-z0-9][A-Za-z0-9._\-]{2,})["'`]""")

_METHOD_HINTS = [
    ("POST", re.compile(r"\b(post|postfor|create|publish|send)\w*\(", re.I)),
    ("PUT", re.compile(r"\b(put|update)\w*\(", re.I)),
    ("DELETE", re.compile(r"\b(delete|remove)\w*\(", re.I)),
    ("PATCH", re.compile(r"\bpatch\w*\(", re.I)),
    ("GET", re.compile(r"\b(get|getfor|fetch|retrieve|exchange)\w*\(", re.I)),
]

_PROTO_HINTS = [
    ("kafka", re.compile(r"kafka|streambridge|kstream|sarama|producermessage|kafka\.writer", re.I)),
    ("rabbitmq", re.compile(r"rabbit|amqp|basicpublish", re.I)),
    ("grpc", re.compile(r"grpc|\bstub\b|\.newcall\(", re.I)),
    ("websocket", re.compile(r"websocket|\.sendtext\(", re.I)),
    ("graphql", re.compile(r"graphql|\bgql\b", re.I)),
    ("dubbo", re.compile(r"dubbo|\$invoke", re.I)),
]

_PUBLISH_RE = re.compile(r"\b(send|publish|produce|emit|dispatch|enqueue)\w*\(", re.I)
# quoted dotted/hyphenated token that looks like a topic/queue/subject name
_NAMED_TOPIC_RE = re.compile(r"""["'`]([A-Za-z][A-Za-z0-9]*(?:[.\-_][A-Za-z0-9]+)+)["'`]""")


# ---------------------------------------------------------------------------
# public
# ---------------------------------------------------------------------------

def extract_interservice(service, run_codeql: bool = True, refresh: bool = False) -> Dict:
    service.workdir.mkdir(parents=True, exist_ok=True)
    out_file = service.workdir / INTERSERVICE_JSON
    if out_file.exists() and not refresh:
        return json.loads(out_file.read_text())

    calls: List[Dict] = []
    if run_codeql:
        calls = _run_interservice_codeql(service)
    if not calls:
        calls = _heuristic_outbound(service)

    for i, c in enumerate(calls):
        c.setdefault("id", f"out_{i}")

    payload = {
        "service": service.name,
        "service_key": service.key,
        "language": service._safe_language(),
        "source": "codeql" if run_codeql and calls and calls[0].get("_via") == "codeql" else "heuristic",
        "outbound_calls": calls,
    }
    for c in calls:
        c.pop("_via", None)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(payload, indent=2))
    return payload


def extract_endpoints(service, run_codeql: bool = True, refresh: bool = False) -> Dict:
    service.workdir.mkdir(parents=True, exist_ok=True)
    out_file = service.workdir / ENDPOINTS_JSON
    if out_file.exists() and not refresh:
        return json.loads(out_file.read_text())

    eps: List[Dict] = []
    if run_codeql:
        eps = _run_endpoints_codeql(service)
    if not eps:
        eps = _heuristic_endpoints(service)

    seen = set()
    uniq = []
    for e in eps:
        k = (e.get("protocol"), e.get("method"), e.get("route"), e.get("file"), e.get("line"))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(e)
    for i, e in enumerate(uniq):
        e.setdefault("id", f"ep_{i}")
        e.pop("_via", None)

    payload = {
        "service": service.name,
        "service_key": service.key,
        "language": service._safe_language(),
        "endpoints": uniq,
    }
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(payload, indent=2))
    return payload


# ---------------------------------------------------------------------------
# CodeQL path
# ---------------------------------------------------------------------------

def _run_query(query: Path, service, sarif_out: Path) -> Optional[Path]:
    if execute_query is None or not query.exists() or not Path(service.database_dir).exists():
        return None
    ok = execute_query(
        query_path=query,
        database_path=Path(service.database_dir),
        output_file=sarif_out,
        query_wd=query.parent,
        rerun=False,  # read-only extraction — let CodeQL cache
    )
    return sarif_out if ok and sarif_out.exists() else None


def _iter_messages(sarif_file: Path):
    for res in stream_sarif_results(sarif_file):
        msg = (res.get("message", {}) or {}).get("text", "") or ""
        loc = {}
        locs = res.get("locations") or []
        if locs:
            loc = extract_sarif_location(locs[0])
        yield msg, loc


def _run_interservice_codeql(service) -> List[Dict]:
    lang = service._safe_language()
    if not lang:
        return []
    sarif = _run_query(get_interservice_query(lang), service, (service.workdir / INTERSERVICE_SARIF))
    if not sarif:
        return []
    calls = []
    for msg, loc in _iter_messages(sarif):
        rec = _parse_inter_message(msg)
        if rec is None:
            continue
        rec.setdefault("file", loc.get("file", ""))
        rec.setdefault("line", loc.get("start_line", 0))
        rec.setdefault("location", f"{rec['file']}:{rec['line']}")
        rec["_via"] = "codeql"
        calls.append(rec)
    return calls


def _run_endpoints_codeql(service) -> List[Dict]:
    lang = service._safe_language()
    if not lang:
        return []
    sarif = _run_query(get_endpoints_query(lang), service, (service.workdir / ENDPOINTS_SARIF))
    if not sarif:
        return []
    eps = []
    for msg, loc in _iter_messages(sarif):
        rec = _parse_endpoint_message(msg)
        if rec is None:
            continue
        rec.setdefault("file", loc.get("file", ""))
        rec.setdefault("line", loc.get("start_line", 0))
        rec["_via"] = "codeql"
        eps.append(rec)
    return eps


def _undouble_braces(s: str) -> str:
    # CodeQL SARIF message formatting doubles literal { } — undo it.
    return s.replace("{{", "{").replace("}}", "}")


# constant strings that are captured as call arguments but are not channels
_NON_CHANNEL = {
    "get", "post", "put", "delete", "patch", "head", "options",
    "application/json", "application/xml", "text/plain", "text/html",
    "application/x-www-form-urlencoded", "multipart/form-data", "utf-8",
}


def _is_channel_like(ch: str) -> bool:
    ch = ch.strip()
    if not ch or ch.lower() in _NON_CHANNEL:
        return False
    if ch.startswith("{") or "\n" in ch:          # a request/GraphQL body, not an id
        return False
    if " " in ch and "://" not in ch:             # free text, not a URL/path/topic
        return False
    return True


def _parse_inter_message(msg: str) -> Optional[Dict]:
    # INTER|<protocol>|<method>|<channel>|<file>:<line>|<name>@<file>:<startline>
    if not msg.startswith("INTER|"):
        return None
    msg = _undouble_braces(msg)
    parts = msg.split("|")
    if len(parts) < 6:
        return None
    _, proto, method, channel, callloc, enclosing = parts[:6]
    channel = channel.split("\n", 1)[0].strip()
    enclosing = enclosing.split("\n", 1)[0].strip()   # guard against message-run-on
    if not _is_channel_like(channel):
        return None
    file, _, line = callloc.rpartition(":")
    return {
        "protocol": (proto or "http").strip().lower() or "http",
        "method": (method or "").strip().upper() or None,
        "channel": channel,
        "file": file.strip(),
        "line": int(line) if line.strip().isdigit() else 0,
        "location": callloc.strip(),
        "enclosing_function": enclosing,
    }


def _parse_endpoint_message(msg: str) -> Optional[Dict]:
    # ENDPOINT|<protocol>|<method>|<route>|<name>@<file>:<startline>
    if not msg.startswith("ENDPOINT|"):
        return None
    msg = _undouble_braces(msg)
    parts = msg.split("|")
    if len(parts) < 5:
        return None
    _, proto, method, route, handler = parts[:5]
    name = handler.split("@", 1)[0]
    floc = handler.split("@", 1)[1] if "@" in handler else ""
    file, _, line = floc.rpartition(":")
    return {
        "protocol": (proto or "http").strip().lower() or "http",
        "method": (method or "").strip().upper() or None,
        "route": route.strip() or "/",
        "handler": handler.strip(),
        "handler_name": name.strip(),
        "file": file.strip(),
        "line": int(line) if line.strip().isdigit() else 0,
    }


# ---------------------------------------------------------------------------
# heuristic fallbacks
# ---------------------------------------------------------------------------

def _infer_method(text: str) -> Optional[str]:
    for m, rx in _METHOD_HINTS:
        if rx.search(text):
            return m
    return None


def _infer_proto(text: str) -> str:
    for p, rx in _PROTO_HINTS:
        if rx.search(text):
            return p
    return "http"


def _heuristic_outbound(service) -> List[Dict]:
    """Derive outbound channels from an already-computed Flow2Out.json."""
    f2o = service.workdir / F_OUT
    if not f2o.exists():
        return []
    try:
        data = json.loads(f2o.read_text())
    except Exception:
        return []

    calls: List[Dict] = []
    for _key, flows in (data.get("grouped_flows") or {}).items():
        for flow in flows:
            steps = flow.get("steps") or []
            if not steps:
                continue
            sink = steps[-1]
            stmt = sink.get("statement", "") or ""
            proto = _infer_proto(stmt)
            method = _infer_method(stmt)
            func_id = sink.get("function_id") or "N/A"

            channels = _URL_RE.findall(stmt)
            if not channels:
                channels = list(_STR_RE.findall(stmt))
            if not channels and (proto in ("kafka", "rabbitmq") or _PUBLISH_RE.search(stmt)):
                topics = _NAMED_TOPIC_RE.findall(stmt) or [
                    t for t in _TOPIC_RE.findall(stmt) if any(c in t for c in "._-")
                ]
                channels = topics[:1]
                if channels and proto == "http":
                    proto = "kafka"
            if not channels:
                continue
            for ch in dict.fromkeys(channels):
                calls.append({
                    "protocol": proto,
                    "method": method,
                    "channel": ch,
                    "file": sink.get("file", ""),
                    "line": int(str(sink.get("location", ":0")).rsplit(":", 1)[-1] or 0)
                    if sink.get("location") else 0,
                    "location": sink.get("location", ""),
                    "enclosing_function": func_id if func_id != "N/A" else "",
                    "source_location": flow.get("source_location", ""),
                    "flow_ref": flow.get("flow_id", ""),
                })
    return calls


_SRC_GLOBS = {
    "java": ("*.java",),
    "python": ("*.py",),
    "go": ("*.go",),
    "javascript": ("*.js", "*.mjs", "*.ts"),
    "typescript": ("*.ts",),
    "csharp": ("*.cs",),
    "cpp": ("*.cc", "*.cpp", "*.cxx"),
}

# framework-agnostic route decorators / annotations
_ROUTE_PATTERNS = [
    # Java Spring:  @PostMapping("/x")  @RequestMapping(value="/x", method=POST)
    (re.compile(r"""@(Get|Post|Put|Delete|Patch|Request)Mapping\(\s*(?:value\s*=\s*|path\s*=\s*)?["']([^"']+)["']""", re.I),
     lambda m: (m.group(1).upper().replace("REQUEST", ""), m.group(2))),
    # Python FastAPI / Flask-restx:  @router.post("/x")  @app.get("/x")
    (re.compile(r"""@\w+\.(get|post|put|delete|patch|route)\(\s*["']([^"']+)["']""", re.I),
     lambda m: (m.group(1).upper() if m.group(1).lower() != "route" else None, m.group(2))),
    # Flask:  @app.route("/x", methods=["POST"])
    (re.compile(r"""@\w+\.route\(\s*["']([^"']+)["'](?:[^)]*methods\s*=\s*\[([^\]]*)\])?""", re.I),
     lambda m: ((m.group(2) or "").strip().strip("\"'").upper().split(",")[0].strip() or None, m.group(1))),
    # Go gin/echo/mux/chi:  r.POST("/x", ...)  e.GET("/x", ...)  mux.HandleFunc("/x", ...)
    (re.compile(r"""\.(GET|POST|PUT|DELETE|PATCH|HandleFunc|Handle)\(\s*["']([^"']+)["']"""),
     lambda m: (None if m.group(1) in ("HandleFunc", "Handle") else m.group(1).upper(), m.group(2))),
    # Express:  app.post("/x", ...)  router.get('/x', ...)
    (re.compile(r"""\b(?:app|router)\.(get|post|put|delete|patch|all)\(\s*["']([^"']+)["']"""),
     lambda m: (m.group(1).upper() if m.group(1) != "all" else None, m.group(2))),
    # ASP.NET:  [HttpPost("x")]  [Route("x")]
    (re.compile(r"""\[Http(Get|Post|Put|Delete|Patch)\(\s*["']([^"']+)["']\s*\)\]""", re.I),
     lambda m: (m.group(1).upper(), m.group(2))),
]

_HANDLER_NAME_RE = re.compile(
    r"""(?:def|func|fn)\s+([A-Za-z_]\w*)"""            # python / go / rust-ish
    r"""|(?:public|private|protected|internal|static|async|\s)+[\w<>\[\],.?]+\s+([A-Za-z_]\w*)\s*\("""  # java/c#
    r"""|(?:const|let|var|function)\s+([A-Za-z_]\w*)\s*=?"""  # js
)


def _heuristic_endpoints(service) -> List[Dict]:
    root = Path(service.source_dir)
    lang = (service._safe_language() or "").lower()
    globs = _SRC_GLOBS.get(lang, ("*.py", "*.java", "*.go", "*.js", "*.ts", "*.cs"))

    eps: List[Dict] = []
    files: List[Path] = []
    for g in globs:
        files.extend(root.rglob(g))
    for fp in files:
        rel = str(fp.relative_to(root))
        if _VENDOR.search("/" + rel):
            continue
        try:
            lines = fp.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue

        class_prefix = ""
        cm = None
        for ln in lines[:400]:
            cm = re.search(r"""@RequestMapping\(\s*(?:value\s*=\s*|path\s*=\s*)?["']([^"']+)["']""", ln)
            if cm:
                class_prefix = cm.group(1)
                break

        for idx, ln in enumerate(lines):
            for rx, fn in _ROUTE_PATTERNS:
                m = rx.search(ln)
                if not m:
                    continue
                try:
                    method, route = fn(m)
                except Exception:
                    continue
                if not route:
                    continue
                name, hline = _find_handler(lines, idx)
                # a class-level @RequestMapping("/api") is a route *prefix*, not an
                # endpoint: verb-less and its path is exactly the detected prefix.
                if not method and class_prefix and route.strip("/") == class_prefix.strip("/"):
                    continue
                if class_prefix and not route.startswith(class_prefix):
                    route = "/" + (class_prefix.strip("/") + "/" + route.strip("/")).strip("/")
                eps.append({
                    "protocol": "http",
                    "method": (method or None),
                    "route": route if route.startswith("/") else "/" + route,
                    "handler": f"{name}@{rel}:{hline}" if name else f"{rel}:{idx + 1}",
                    "handler_name": name or "",
                    "file": rel,
                    "line": hline,
                    "_via": "heuristic",
                })
    return eps


def _find_handler(lines: List[str], decorator_idx: int) -> tuple:
    """Look downward from a route decorator for the handler function name."""
    for j in range(decorator_idx, min(decorator_idx + 8, len(lines))):
        m = _HANDLER_NAME_RE.search(lines[j])
        if m:
            name = next((g for g in m.groups() if g), None)
            if name and name.lower() not in ("if", "for", "return", "new"):
                return name, j + 1
    return "", decorator_idx + 1
