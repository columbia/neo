"""
Code-search primitives (agent.primitives) and the perception-action loop
(agent.loop) — the paper-aligned agentic layer.  No CodeQL / real LLM needed.
"""

import json

import pytest

from agent.loop import AgentLoop
from agent.primitives import CodeSearchEngine, Unsupported
from common.services import Application, Service


# --------------------------------------------------------------------------- #
# fakes
# --------------------------------------------------------------------------- #

class FakeConn:
    def __init__(self, calls):
        self._calls = calls

    def execute(self, sql, params=None):
        class _Cur:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows
        # only qast("call") uses .conn.execute
        return _Cur([(c["callsite_id"], c["target"]) for c in self._calls])


class FakeDB:
    def __init__(self):
        self.funcs = [
            {"function_id": "update_role@app/main.py:30", "name": "update_role",
             "file_path": "app/main.py", "start_line": 30, "end_line": 40,
             "signature": "def update_role(username, role)", "class_name": None, "package_name": None},
            {"function_id": "get_user@app/main.py:5", "name": "get_user",
             "file_path": "app/main.py", "start_line": 5, "end_line": 9,
             "signature": "def get_user(id)", "class_name": None, "package_name": None},
            {"function_id": "set_user_role@app/api.py:12", "name": "set_user_role",
             "file_path": "app/api.py", "start_line": 12, "end_line": 20,
             "signature": None, "class_name": "Api", "package_name": None},
        ]
        self.calls = [{"callsite_id": "update_role@app/api.py:16", "target": "update_role@app/main.py:30"}]
        self.conn = FakeConn(self.calls)

    def _match(self, pat):
        import re
        rx = re.compile(pat)
        return [f for f in self.funcs if rx.search(f["name"])]

    def search_functions_by_name(self, pattern, limit=200):
        return self._match(pattern)[:limit]

    def search_classes_by_name(self, pattern, limit=200):
        return []

    def all_functions(self, limit=5000):
        return list(self.funcs)[:limit]

    def get_functions_by_name(self, name):
        return [f for f in self.funcs if f["name"] == name]

    def get_function_definition(self, fid):
        return next((f for f in self.funcs if f["function_id"] == fid), None)

    def get_callees(self, fid):
        return []

    def get_callers(self, fid):
        if fid == "update_role@app/main.py:30":
            return [dict(self.funcs[2], callsite="update_role@app/api.py:16")]
        return []

    def get_function_by_identifier(self, ident, source_root=None):
        f = self.get_function_definition(ident)
        return [f] if f else []

    def get_function_source_code(self, info, source_root):
        return f"# source of {info['name']}\n... writes {info['name']} ..."

    def close(self):
        pass


@pytest.fixture
def engine(tmp_path, monkeypatch):
    svc = Service(name="user-mgmt", role="gateway", app="user-mgmt",
                  source_dir=tmp_path / "user-mgmt", database_dir=tmp_path / "user-mgmt",
                  _language="python")
    (svc.workdir).mkdir(parents=True)
    (svc.workdir / "FlowSourceSink.json").write_text(json.dumps({"grouped_flows": {
        "app/main.py:35": [{
            "flow_id": "f", "source_location": "app/main.py:32", "sink_location": "app/main.py:35",
            "steps": [
                {"statement": "data = request.json", "function_id": "set_user_role@app/api.py:12",
                 "location": "app/main.py:32"},
                {"statement": "update_role(u, r)", "function_id": "update_role@app/main.py:30",
                 "location": "app/main.py:35"},
            ],
        }]
    }}))
    (svc.workdir / "endpoints.json").write_text(json.dumps({"endpoints": [
        {"route": "/setUserRole", "method": "POST", "handler": "set_user_role@app/api.py:12",
         "file": "app/api.py", "line": 12}]}))
    (svc.workdir / "interservice.json").write_text(json.dumps({"outbound_calls": []}))

    app = Application(name="demo", services=[svc])
    eng = CodeSearchEngine(app)
    fake = FakeDB()
    monkeypatch.setattr(eng, "_get_db", lambda name=None: fake)
    return eng


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #

def test_qname_regex(engine):
    hits = engine.qname("user-mgmt", "(?i)(set|update).*role")
    names = {h["name"] for h in hits}
    assert names == {"update_role", "set_user_role"}
    assert all(h["kind"] == "function" and "@" in h["id"] for h in hits)


def test_qast_method_and_call_and_unsupported(engine):
    assert len(engine.qast("user-mgmt", "method")) == 3
    calls = engine.qast("user-mgmt", "call")
    assert calls and calls[0]["target"] == "update_role@app/main.py:30"
    u = engine.qast("user-mgmt", "field_access")
    assert isinstance(u, Unsupported) and "field_access" in u["unsupported"]


def test_qcg_callers(engine):
    callers = engine.qcg("user-mgmt", "update_role", "callers")
    assert callers and callers[0]["name"] == "set_user_role"
    assert callers[0]["callsite"] == "update_role@app/api.py:16"


def test_qflow_approximate_matches_computed_flow(engine):
    flows = engine.qflow("user-mgmt", "request", "update_role")
    assert flows and flows[0]["approximate"] is True
    assert flows[0]["sink_location"] == "app/main.py:35"
    assert engine.qflow("user-mgmt", "request", "no_such_sink") == []


def test_qsource_lists_flow_sources_and_endpoints(engine):
    src = engine.qsource("user-mgmt")
    kinds = {s.get("role", "source") for s in src}
    assert "endpoint" in kinds
    assert any(s.get("location") == "app/main.py:32" for s in src)


def test_get_source_and_get_type(engine):
    el = {"id": "update_role@app/main.py:30", "service": "user-mgmt",
          "signature": "def update_role(username, role)"}
    assert "writes update_role" in engine.get_source("user-mgmt", el)
    assert engine.get_type("user-mgmt", el) == "def update_role(username, role)"
    assert engine.get_type("user-mgmt", {"id": "set_user_role@app/api.py:12"}) == "unknown"


# --------------------------------------------------------------------------- #
# bash() — the read-only fallback tool
# --------------------------------------------------------------------------- #

def test_bash_runs_an_allowlisted_command_in_the_service_root(engine):
    (engine.app.services[0].source_dir / "notes.txt").write_text("TODO: check role header\n")
    out = engine.bash("user-mgmt", "grep -n role notes.txt")
    assert out["exit_code"] == 0
    assert "TODO: check role header" in out["stdout"]
    assert out["cwd"] == "services/user-mgmt"


def test_bash_supports_a_pipeline(engine):
    (engine.app.services[0].source_dir / "a.txt").write_text("one\ntwo\nthree\n")
    out = engine.bash("user-mgmt", "cat a.txt | head -2")
    assert out["stdout"].splitlines() == ["one", "two"]


@pytest.mark.parametrize("command,fragment", [
    ("rm -rf .", "not in the read-only allowlist"),
    ("xargs cat", "not in the read-only allowlist"),
    ("awk '{print}'", "not in the read-only allowlist"),
    ("cat /etc/passwd", "escapes the service's source tree"),
    ("cat ../../etc/hosts", "escapes the service's source tree"),
    ("echo hi > out.txt", "redirection"),
    ("cat $(echo x)", "redirection"),
    ("cat `echo x`", "redirection"),
    ("sed -i s/a/b/ x.txt", "may not be used with"),
    ("find . -exec cat {} +", "may not be used with"),
    ("", "empty command"),
])
def test_bash_rejects_unsafe_commands(engine, command, fragment):
    out = engine.bash("user-mgmt", command)
    assert "error" in out and fragment in out["error"]


def test_bash_can_be_disabled(engine, monkeypatch):
    monkeypatch.setenv("NEO_AGENT_BASH", "0")
    out = engine.bash("user-mgmt", "ls")
    assert out == {"error": "bash fallback is disabled (NEO_AGENT_BASH=0)"}


def test_bash_is_registered_as_an_agent_loop_tool(engine):
    loop = AgentLoop(llm=None, engine=engine)
    assert "bash" in loop.tool_names()


# --------------------------------------------------------------------------- #
# loop
# --------------------------------------------------------------------------- #

class ScriptLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def messages_create(self, history, message, **kw):
        self.calls.append((history, message))
        text = self.replies.pop(0) if self.replies else "<final>{}</final>"

        class R:
            def __init__(self, t):
                self.content = [type("B", (), {"text": t})()]
        return R(text)


def test_loop_dispatches_actions_then_final(engine):
    llm = ScriptLLM([
        '<action name="qname">{"service":"user-mgmt","name":"update.*"}</action>',
        '<action name="get_source">{"service":"user-mgmt","element":{"id":"update_role@app/main.py:30"}}</action>',
        '<final>{"privileged_operations":[{"service":"user-mgmt","name":"update_role",'
        '"id":"update_role@app/main.py:30","file":"app/main.py","line":30,'
        '"category":"role-change","why":"writes role with no check"}]}</final>',
    ])
    loop = AgentLoop(llm, engine, max_iterations=6)
    out = loop.run("find privileged ops")
    assert out["stopped"] == "final"
    assert out["iterations"] == 3
    ops = out["final"]["privileged_operations"]
    assert ops[0]["name"] == "update_role"
    # the get_source observation was fed back
    assert any("writes update_role" in t["content"] for t in out["transcript"] if t["role"] == "observation")


def test_loop_dispatches_bash_action(engine):
    """The exact path a real LLM's <action name="bash"> takes: regex-parsed
    out of the reply text, routed through AgentLoop._dispatch, and fed back
    as an <observation> — not a direct engine.bash() call."""
    (engine.app.services[0].source_dir / "notes.txt").write_text("check ROLE_HEADER here\n")
    llm = ScriptLLM([
        '<action name="bash">{"service":"user-mgmt","command":"grep -rn ROLE_HEADER ."}</action>',
        '<final>{"privileged_operations":[]}</final>',
    ])
    out = AgentLoop(llm, engine, max_iterations=4).run("find privileged ops")
    assert out["stopped"] == "final"
    obs = [t["content"] for t in out["transcript"] if t["role"] == "observation"][0]
    assert "ROLE_HEADER" in obs and "notes.txt" in obs


def test_loop_survives_bad_json_and_unknown_tool(engine):
    llm = ScriptLLM([
        '<action name="nope">{}</action><action name="qname">{not json}</action>',
        '<final>{"privileged_operations":[]}</final>',
    ])
    out = AgentLoop(llm, engine, max_iterations=4).run("x")
    assert out["stopped"] == "final"
    obs = [t["content"] for t in out["transcript"] if t["role"] == "observation"][0]
    assert "unknown tool" in obs


def test_loop_stops_at_max_iterations(engine):
    llm = ScriptLLM(['<action name="qsource">{"service":"user-mgmt"}</action>'] * 10)
    out = AgentLoop(llm, engine, max_iterations=3).run("x")
    assert out["stopped"] == "max_iterations"
    assert out["iterations"] == 3


def test_agent_run_writes_per_service(engine, tmp_path, monkeypatch):
    from agent import run as agent_run

    monkeypatch.setattr(agent_run, "load_application", lambda a: engine.app)
    monkeypatch.setattr(agent_run, "CodeSearchEngine", lambda app: engine)
    monkeypatch.setattr(agent_run, "get_app_description", lambda a: "a user management service")

    llm = ScriptLLM([
        '<final>{"privileged_operations":[{"service":"user-mgmt","name":"update_role",'
        '"id":"update_role@app/main.py:30","file":"app/main.py","line":30,"category":"role-change",'
        '"why":"no eligibility check"}]}</final>',
    ])
    res = agent_run.agent_find_privileged_ops("demo", llm, max_iterations=3)
    assert res["privileged_operations"][0]["name"] == "update_role"

    out = json.loads((engine.app.services[0].workdir / "agent_privileged_ops.json").read_text())
    assert out["privileged_operations"][0]["id"] == "update_role@app/main.py:30"


# --------------------------------------------------------------------------- #
# duck_db.function_index — used by --find-flows and the agent primitives
# --------------------------------------------------------------------------- #

def test_function_index_add_and_load(tmp_path):
    from duck_db.function_index import OptimizedFunctionIndex

    idx = OptimizedFunctionIndex()
    idx.add_functions([
        {"function_id": "f@a.py:10", "name": "f", "file_path": "a.py",
         "start_line": 10, "end_line": 20, "signature": "def f()"},
    ])

    class _EF:  # mimics codeql_function_mapper.EnhancedFunction
        function_id = "g@b.py:5"
        start_line, end_line, file_path = 5, 8, "b.py"

        def to_dict(self):
            return {"function_id": self.function_id, "name": "g", "file_path": "b.py",
                    "start_line": 5, "end_line": 8}

    idx.add_functions([_EF()])
    assert idx.get_function_by_id("f@a.py:10")["name"] == "f"
    assert idx.get_function_containing_line("b.py", 6) == "g@b.py:5"

    out = tmp_path / "fm.json"
    idx.save_optimized_mapping(out)
    reloaded = OptimizedFunctionIndex.load_from_file(out)
    assert reloaded.get_function_containing_line("a.py", 15) == "f@a.py:10"
