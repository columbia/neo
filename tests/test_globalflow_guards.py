"""
Regression guards for the graph builder's conservatism:

* an inbound endpoint is wired only to tainted sources in its *own* handler
  file, not to every source in the receiving service (which would fabricate
  cross-service flows through unrelated code);
* a channel that matches no endpoint produces no inter-service edge.
"""

import json

from common.services import Application, Service
from interlang.graph import build_graph
from interlang.stitch import stitch


def _seed(svc, files):
    wd = svc.source_dir / "neo-workdir"
    wd.mkdir(parents=True, exist_ok=True)
    for name, obj in files.items():
        (wd / name).write_text(json.dumps(obj))


def _svc(tmp_path, name, lang, role="internal", aliases=()):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    return Service(name=name, role=role, app=name, source_dir=d, database_dir=d,
                   aliases=list(aliases), _language=lang)


def _s2s(src, sink, fn):
    return {"grouped_flows": {sink: [{
        "flow_id": "f", "source_location": src, "sink_location": sink,
        "steps": [
            {"step_role": "Step 1", "statement": "src", "location": src,
             "file": src.split(":")[0], "function_id": fn, "role": "source"},
            {"step_role": "Step 2", "statement": "sink", "location": sink,
             "file": sink.split(":")[0], "function_id": fn, "role": "sink"},
        ],
    }]}}


def test_endpoint_does_not_link_unrelated_sources(tmp_path):
    gw = _svc(tmp_path, "gw", "java", role="gateway")
    api = _svc(tmp_path, "api", "python", aliases=["localhost:9000"])

    _seed(gw, {
        "FlowSourceSink.json": {"grouped_flows": {}},
        "Flow2Out.json": {"grouped_flows": {"g.java:1": [{
            "flow_id": "g0", "source_location": "g.java:1", "sink_location": "g.java:3",
            "steps": [{"step_role": "Step 1", "statement": "x", "location": "g.java:1",
                       "file": "g.java", "function_id": "h@g.java:1", "role": "source"},
                      {"step_role": "Step 2", "statement": 'client.post("http://localhost:9000/orders", x)',
                       "location": "g.java:3", "file": "g.java", "function_id": "h@g.java:1", "role": "sink"}],
        }]}},
        "interservice.json": {"outbound_calls": [{
            "id": "out_0", "protocol": "http", "method": "POST",
            "channel": "http://localhost:9000/orders", "file": "g.java", "line": 3,
            "location": "g.java:3", "flow_ref": "g0",
        }]},
        "endpoints.json": {"endpoints": []},
    })
    _seed(api, {
        # two unrelated privileged flows in DIFFERENT files
        "FlowSourceSink.json": {"grouped_flows": {
            "orders.py:9": _s2s("orders.py:6", "orders.py:9", "create_order@orders.py:5")["grouped_flows"]["orders.py:9"],
            "admin.py:20": _s2s("admin.py:15", "admin.py:20", "reset_db@admin.py:14")["grouped_flows"]["admin.py:20"],
        }},
        "Flow2Out.json": {"grouped_flows": {}},
        "interservice.json": {"outbound_calls": []},
        "endpoints.json": {"endpoints": [{
            "id": "ep_0", "protocol": "http", "method": "POST", "route": "/orders",
            "handler": "create_order@orders.py:5", "handler_name": "create_order",
            "file": "orders.py", "line": 5,
        }]},
    })
    app = Application(name="guard", services=[gw, api])
    g = build_graph(app)
    doc = stitch(app, g)
    flows = [f for fl in doc["grouped_flows"].values() for f in fl]

    assert flows, "the legitimate gw -> api/orders flow should still stitch"
    sinks = {f["sink_location"] for f in flows}
    assert sinks == {"services/api/orders.py:9"}
    # admin.py:20 (reset_db) must NOT be reachable from the /orders endpoint
    assert "services/api/admin.py:20" not in sinks


def test_unmatched_channel_makes_no_edge(tmp_path):
    gw = _svc(tmp_path, "gw", "go", role="gateway")
    other = _svc(tmp_path, "other", "python")

    _seed(gw, {
        "FlowSourceSink.json": {"grouped_flows": {}},
        "Flow2Out.json": {"grouped_flows": {"g.go:1": [{
            "flow_id": "g0", "source_location": "g.go:1", "sink_location": "g.go:2",
            "steps": [{"step_role": "Step 1", "statement": "x", "location": "g.go:1",
                       "file": "g.go", "function_id": "N/A", "role": "source"},
                      {"step_role": "Step 2", "statement": 'http.Post("http://other/nonexistent/path", ...)',
                       "location": "g.go:2", "file": "g.go", "function_id": "N/A", "role": "sink"}],
        }]}},
        "interservice.json": {"outbound_calls": [{
            "id": "out_0", "protocol": "http", "method": "POST",
            "channel": "http://other/nonexistent/path", "file": "g.go", "line": 2,
            "location": "g.go:2", "flow_ref": "g0",
        }]},
        "endpoints.json": {"endpoints": []},
    })
    _seed(other, {
        "FlowSourceSink.json": _s2s("h.py:3", "h.py:6", "handler@h.py:2"),
        "Flow2Out.json": {"grouped_flows": {}},
        "interservice.json": {"outbound_calls": []},
        "endpoints.json": {"endpoints": [{
            "id": "ep_0", "protocol": "http", "method": "GET", "route": "/totally/different",
            "handler": "handler@h.py:2", "handler_name": "handler", "file": "h.py", "line": 2,
        }]},
    })
    app = Application(name="nomatch", services=[gw, other])
    g = build_graph(app)
    assert not [e for e in g.edges if e.kind == "inter_call"]
    assert stitch(app, g)["summary"]["total_flows"] == 0
