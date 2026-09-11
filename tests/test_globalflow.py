"""
End-to-end (offline) test of the cross-service engine on the paper's motivating
example: a Java `UserProfile` service forwards a role-update to a Python
`UserMgmt` service, whose privileged `update_role` sink is reachable from the
Java entry point.
"""

import json

import pytest

from common.services import Application, Service
from interlang import extract as extract_mod
from interlang.graph import BOUNDARY, ENDPOINT_N, SINK, build_graph
from interlang.stitch import stitch


def _write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2))


@pytest.fixture
def app(tmp_path):
    up_src = tmp_path / "userprofile-java"
    um_src = tmp_path / "usermgmt-python"
    (up_src / "src").mkdir(parents=True)
    um_src.mkdir(parents=True)

    # a real FastAPI-ish handler so the heuristic endpoint scanner has something
    (um_src / "main.py").write_text(
        "from fastapi import APIRouter, Request\n"
        "router = APIRouter()\n"
        "\n"
        '@router.post("/setUserRole")\n'
        "async def set_user_role(request: Request):\n"
        "    data = await request.json()\n"
        "    update_role(data['username'], data['role'])\n"
    )

    up_wd = up_src / "neo-workdir"
    um_wd = um_src / "neo-workdir"

    # --- user-profile (java, gateway): source -> outbound HTTP call ----------
    _write(up_wd / "FlowSourceSink.json", {"grouped_flows": {}})
    _write(up_wd / "Flow2Out.json", {
        "grouped_flows": {
            "src/ProfileController.java:4": [{
                "flow_id": "flow_0_0_0",
                "source_location": "src/ProfileController.java:4",
                "sink_location": "src/ProfileController.java:14",
                "steps": [
                    {"step_role": "Step 1 [SOURCE]", "statement": "String role = req.getRole();",
                     "location": "src/ProfileController.java:4", "file": "src/ProfileController.java",
                     "function_id": "updateProfile@src/ProfileController.java:3", "role": "source"},
                    {"step_role": "Step 2 [SINK]",
                     "statement": 'restTemplate.postForObject("http://localhost:5000/setUserRole", entity, String.class);',
                     "location": "src/ProfileController.java:14", "file": "src/ProfileController.java",
                     "function_id": "updateProfile@src/ProfileController.java:3", "role": "sink"},
                ],
            }]
        }
    })
    _write(up_wd / "interservice.json", {
        "outbound_calls": [{
            "id": "out_0", "protocol": "http", "method": "POST",
            "channel": "http://localhost:5000/setUserRole",
            "file": "src/ProfileController.java", "line": 14,
            "location": "src/ProfileController.java:14",
            "enclosing_function": "updateProfile@src/ProfileController.java:3",
            "flow_ref": "flow_0_0_0",
        }],
    })
    _write(up_wd / "endpoints.json", {"endpoints": []})

    # --- user-mgmt (python, internal): request -> privileged update_role -----
    _write(um_wd / "FlowSourceSink.json", {
        "grouped_flows": {
            "main.py:22": [{
                "flow_id": "flow_0_0_0",
                "source_location": "main.py:20",
                "sink_location": "main.py:22",
                "steps": [
                    {"step_role": "Step 1 [SOURCE]", "statement": "data = await request.json()",
                     "location": "main.py:20", "file": "main.py",
                     "function_id": "set_user_role@main.py:19", "role": "source"},
                    {"step_role": "Step 2 [SINK]", "statement": "update_role(data['username'], data['role'])",
                     "location": "main.py:22", "file": "main.py",
                     "function_id": "set_user_role@main.py:19", "role": "sink"},
                ],
            }]
        }
    })
    _write(um_wd / "Flow2Out.json", {"grouped_flows": {}})
    _write(um_wd / "interservice.json", {"outbound_calls": []})
    _write(um_wd / "endpoints.json", {
        "endpoints": [{
            "id": "ep_0", "protocol": "http", "method": "POST", "route": "/setUserRole",
            "handler": "set_user_role@main.py:19", "handler_name": "set_user_role",
            "file": "main.py", "line": 19,
        }],
    })

    services = [
        Service(name="user-profile", role="gateway", app="userprofile-java",
                source_dir=up_src, database_dir=up_src, _language="java"),
        Service(name="user-mgmt", role="internal", app="usermgmt-python",
                source_dir=um_src, database_dir=um_src, aliases=["localhost:5000"], _language="python"),
    ]
    return Application(name="role-switch-demo", services=services)


def test_graph_has_cross_service_edge(app):
    g = build_graph(app)

    boundaries = [n for n in g.nodes.values() if n.kind == BOUNDARY]
    endpoints = [n for n in g.nodes.values() if n.kind == ENDPOINT_N]
    sinks = [n for n in g.nodes.values() if n.kind == SINK]
    assert boundaries, "outbound call not modelled"
    assert endpoints, "python endpoint not matched"
    assert any(s.service == "user-mgmt" for s in sinks)

    inter = [e for e in g.edges if e.kind == "inter_call"]
    assert inter, "no outbound->endpoint edge was drawn"
    assert inter[0].data["from_service"] == "user-profile"
    assert inter[0].data["to_service"] == "user-mgmt"
    assert inter[0].score >= 0.9


def test_stitched_flow_spans_both_services(app):
    g = build_graph(app)
    doc = stitch(app, g)

    flows = [f for fl in doc["grouped_flows"].values() for f in fl]
    assert len(flows) >= 1
    f = flows[0]
    assert f["cross_service"] is True
    assert f["hop_count"] == 1
    assert f["services"] == ["user-profile", "user-mgmt"]
    assert f["source_location"].startswith("services/user-profile/")
    assert f["sink_location"].startswith("services/user-mgmt/")
    assert any("[CROSS-SERVICE]" in s["step_role"] for s in f["steps"])
    assert "update_role" in f["steps"][-1]["statement"]


def test_heuristic_extraction_from_flow2out(app):
    """Drop the pre-baked interservice.json; the channel must be recovered
    from Flow2Out.json by the heuristic extractor."""
    up = app.get("user-profile")
    (up.workdir / "interservice.json").unlink()

    payload = extract_mod.extract_interservice(up, run_codeql=False, refresh=True)
    calls = payload["outbound_calls"]
    assert calls, "heuristic did not recover an outbound channel"
    assert calls[0]["channel"] == "http://localhost:5000/setUserRole"
    assert calls[0]["protocol"] == "http"
    assert calls[0]["method"] == "POST"


def test_heuristic_endpoint_scan(app):
    um = app.get("user-mgmt")
    (um.workdir / "endpoints.json").unlink()

    payload = extract_mod.extract_endpoints(um, run_codeql=False, refresh=True)
    routes = {e["route"] for e in payload["endpoints"]}
    assert "/setUserRole" in routes
    ep = next(e for e in payload["endpoints"] if e["route"] == "/setUserRole")
    assert ep["method"] == "POST"
    assert ep["handler_name"] == "set_user_role"


def test_build_global_flows_writes_artifacts(app, tmp_path, monkeypatch):
    """The full offline build path: extraction -> graph -> stitched flow file."""
    from common import helper
    from interlang import run as run_mod

    gdir = tmp_path / "_global"
    monkeypatch.setattr(helper, "get_codebases_dir", lambda: tmp_path)
    # get_global_workdir is imported into run_mod's namespace
    monkeypatch.setattr(run_mod, "get_global_workdir", lambda name: _mk(gdir / name))
    monkeypatch.setattr(run_mod, "get_global_graph_json_file", lambda name: _mk(gdir / name) / "graph.json")
    monkeypatch.setattr(run_mod, "get_global_flow_json_file", lambda name: _mk(gdir / name) / "GlobalFlowSourceSink.json")

    out = run_mod.build_global_flows(app, run_codeql=False)
    assert out.exists()
    doc = json.loads(out.read_text())
    assert doc["summary"]["total_flows"] >= 1
    assert doc["metadata"]["services"] == ["user-profile", "user-mgmt"]


def _mk(p):
    p.mkdir(parents=True, exist_ok=True)
    return p
