"""Coverage for the Python bits not touched by the other suites."""

import json

import pytest

from agent.primitives import CodeSearchEngine
from common.services import Application, Service


# --------------------------------------------------------------------------- #
# gen_flowfromto / gen_astsearch  (pure string transforms)
# --------------------------------------------------------------------------- #

def test_gen_flowfromto_regex_and_unsupported_lang():
    from genquery.gen_flowfromto import _to_codeql_regex, gen_flowfromto_query

    assert _to_codeql_regex("update_role") == "(?i).*update_role.*"
    assert _to_codeql_regex("update.*") == "update.*"        # already a regex
    assert _to_codeql_regex("") == ".*"
    assert gen_flowfromto_query("ruby", "app", "a", "b") is None  # unsupported language


def test_gen_flowfromto_fills_template(tmp_path, monkeypatch):
    from genquery import gen_flowfromto as m

    qdir = tmp_path / "queries" / "java"
    qdir.mkdir(parents=True)
    (qdir / "templateFlowFromTo.ql").write_text("src={{FROM}} sink={{TO}}\n")
    tmp = tmp_path / "tmpq"
    tmp.mkdir()
    monkeypatch.setattr(m, "get_query_dir", lambda: tmp_path / "queries")
    monkeypatch.setattr(m, "get_query_tmp_dir", lambda lang: tmp)

    out = m.gen_flowfromto_query("java", "my-app", "request", "update_role")
    text = out.read_text()
    assert "{{FROM}}" not in text and "{{TO}}" not in text
    assert "request" in text and "update" in text


def test_gen_astsearch_op_normalisation():
    from genquery.gen_astsearch import normalize_op

    assert normalize_op("FIELD") == "field_access"
    assert normalize_op("invocation") == "call"
    assert normalize_op("param") == "parameter"
    assert normalize_op("nonsense") is None


# --------------------------------------------------------------------------- #
# get_source line-window fallback
# --------------------------------------------------------------------------- #

def test_get_source_line_window(tmp_path):
    svc_dir = tmp_path / "svc"
    (svc_dir / "app").mkdir(parents=True)
    (svc_dir / "app" / "main.py").write_text("\n".join(f"line{i}" for i in range(1, 41)))
    app = Application(name="x", services=[
        Service(name="svc", role="gateway", app="svc", source_dir=svc_dir,
                database_dir=svc_dir, _language="python")])
    eng = CodeSearchEngine(app)

    out = eng.get_source("svc", {"file": "app/main.py", "line": 20, "service": "svc"}, context=3)
    lines = out.splitlines()
    assert lines[0] == "17:line17" and lines[-1] == "23:line23"

    # via an id with no matching function -> still windows from the file
    out2 = eng.get_source("svc", {"id": "foo@app/main.py:5", "service": "svc"}, context=2)
    assert "5:line5" in out2
    assert eng.get_source("svc", {"file": "nope.py", "line": 1}) is None


# --------------------------------------------------------------------------- #
# MultiServiceCallGraph dispatch
# --------------------------------------------------------------------------- #

def test_multiservice_callgraph_routes_by_prefix(tmp_path, monkeypatch):
    from interlang import multidb

    class FakeCG:
        def __init__(self, name):
            self.name = name
            self.closed = False

        def get_function_by_identifier(self, ident, source_root=None):
            return [{"function_id": ident, "name": ident.split("@")[0],
                     "file_path": "app/main.py", "_svc": self.name}]

        def get_function_source_code(self, info, root):
            return f"# {self.name}: {info['file_path']}"

        def close(self):
            self.closed = True

    made = {}
    monkeypatch.setattr(multidb, "CallGraphDatabase",
                        lambda p: made.setdefault(p.parent.name, FakeCG(p.parent.name)))
    for d in ("gw", "be"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "callgraph.duckdb").write_text("x")

    m = multidb.MultiServiceCallGraph(
        {"gw": tmp_path / "gw" / "callgraph.duckdb", "be": tmp_path / "be" / "callgraph.duckdb"},
        {"gw": tmp_path / "gw", "be": tmp_path / "be"},
    )
    rows = m.get_function_by_identifier("set_role@services/be/app/main.py:12")
    assert rows[0]["_service"] == "be"
    assert rows[0]["file_path"] == "services/be/app/main.py"   # re-prefixed for display

    code = m.get_function_source_code(rows[0], tmp_path)
    assert code.startswith("# be:")

    # unknown prefix -> aggregate across all dbs
    agg = m.get_function_by_identifier("helper")
    assert {r["_service"] for r in agg} == {"gw", "be"}
    m.close()


# --------------------------------------------------------------------------- #
# merge_into_customize_op
# --------------------------------------------------------------------------- #

def test_merge_into_customize_op_escapes_and_calls_gen(tmp_path, monkeypatch):
    from agent import run as agent_run

    svc = Service(name="svc", role="gateway", app="svc", source_dir=tmp_path / "svc",
                  database_dir=tmp_path / "svc", _language="java")
    svc.workdir.mkdir(parents=True)
    (svc.workdir / "agent_privileged_ops.json").write_text(json.dumps({
        "privileged_operations": [{"name": "setUserRole"}, {"name": "pay.success"}, {"name": ""}]
    }))
    app = Application(name="a", services=[svc])

    calls = {}
    monkeypatch.setattr(agent_run, "load_application", lambda a: app)
    monkeypatch.setattr("common.helper.get_database_language", lambda d: "java")
    monkeypatch.setattr("common.helper.get_app_database_dir", lambda k: tmp_path / "svc")
    monkeypatch.setattr("common.helper.update_status", lambda *a, **k: None)
    monkeypatch.setattr("genquery.gen_callsite.gen_callsite_query",
                        lambda pats, lang, key: calls.update(pats=pats, lang=lang, key=key))

    total = agent_run.merge_into_customize_op("a")
    assert total == 2
    assert calls["lang"] == "java" and calls["key"] == "svc"
    assert set(calls["pats"]) == {"^setUserRole$", "^pay\\.success$"}
