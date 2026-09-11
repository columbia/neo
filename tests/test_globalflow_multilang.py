"""
Cross-language stitching beyond the Java->Python HTTP case:

* a 3-language HTTP chain   (JS gateway -> Go orders -> Python billing)
* a non-HTTP hop           (Go producer -> Kafka topic -> Java consumer)
"""

import json

import pytest

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


def _s2s(src, sink, stmt_src, stmt_sink, fn):
    return {"grouped_flows": {sink: [{
        "flow_id": "f", "source_location": src, "sink_location": sink,
        "steps": [
            {"step_role": "Step 1", "statement": stmt_src, "location": src,
             "file": src.split(":")[0], "function_id": fn, "role": "source"},
            {"step_role": "Step 2", "statement": stmt_sink, "location": sink,
             "file": sink.split(":")[0], "function_id": fn, "role": "sink"},
        ],
    }]}}


def _f2o(src, sink, stmt_sink, fn, flow_id="f"):
    return {"grouped_flows": {src: [{
        "flow_id": flow_id, "source_location": src, "sink_location": sink,
        "steps": [
            {"step_role": "Step 1", "statement": "user input", "location": src,
             "file": src.split(":")[0], "function_id": fn, "role": "source"},
            {"step_role": "Step 2", "statement": stmt_sink, "location": sink,
             "file": sink.split(":")[0], "function_id": fn, "role": "sink"},
        ],
    }]}}


# --------------------------------------------------------------------------- #
# 3-language HTTP chain
# --------------------------------------------------------------------------- #

@pytest.fixture
def http_chain(tmp_path):
    gw = _svc(tmp_path, "web", "javascript", role="gateway")
    orders = _svc(tmp_path, "orders", "go", aliases=["localhost:8081"])
    billing = _svc(tmp_path, "billing", "python", aliases=["localhost:8082"])

    _seed(gw, {
        "FlowSourceSink.json": {"grouped_flows": {}},
        "Flow2Out.json": _f2o("routes.js:10", "routes.js:11",
                              'axios.post("http://localhost:8081/orders/" + id + "/pay", body)',
                              "pay@routes.js:8", flow_id="g0"),
        "interservice.json": {"outbound_calls": [{
            "id": "out_0", "protocol": "http", "method": "POST",
            "channel": "http://localhost:8081/orders/42/pay",
            "file": "routes.js", "line": 11, "location": "routes.js:11",
            "flow_ref": "g0", "enclosing_function": "pay@routes.js:8",
        }]},
        "endpoints.json": {"endpoints": []},
    })
    _seed(orders, {
        "FlowSourceSink.json": {"grouped_flows": {}},
        "Flow2Out.json": _f2o("orders.go:20", "orders.go:22",
                              'http.Post("http://localhost:8082/charge/"+cust, "application/json", b)',
                              "PayOrder@orders.go:15", flow_id="o0"),
        "interservice.json": {"outbound_calls": [{
            "id": "out_0", "protocol": "http", "method": "POST",
            "channel": "http://localhost:8082/charge/cust-1",
            "file": "orders.go", "line": 22, "location": "orders.go:22",
            "flow_ref": "o0", "enclosing_function": "PayOrder@orders.go:15",
        }]},
        "endpoints.json": {"endpoints": [{
            "id": "ep_0", "protocol": "http", "method": "POST", "route": "/orders/{id}/pay",
            "handler": "PayOrder@orders.go:15", "handler_name": "PayOrder",
            "file": "orders.go", "line": 15,
        }]},
    })
    _seed(billing, {
        "FlowSourceSink.json": _s2s("billing.py:5", "billing.py:8",
                                    "amount = request.json['amount']",
                                    "ledger.charge(customer, amount)  # privileged",
                                    "charge@billing.py:4"),
        "Flow2Out.json": {"grouped_flows": {}},
        "interservice.json": {"outbound_calls": []},
        "endpoints.json": {"endpoints": [{
            "id": "ep_0", "protocol": "http", "method": "POST", "route": "/charge/{customer}",
            "handler": "charge@billing.py:4", "handler_name": "charge",
            "file": "billing.py", "line": 4,
        }]},
    })
    return Application(name="shop", services=[gw, orders, billing])


def test_three_language_http_chain(http_chain):
    g = build_graph(http_chain)
    doc = stitch(http_chain, g)
    flows = [f for fl in doc["grouped_flows"].values() for f in fl]

    assert flows, "no cross-service flow stitched"
    full = next((f for f in flows if f["hop_count"] == 2), None)
    assert full is not None, f"expected a 2-hop flow, got {[f['hop_count'] for f in flows]}"
    assert full["services"] == ["web", "orders", "billing"]
    assert full["source_location"].startswith("services/web/")
    assert full["sink_location"].startswith("services/billing/")
    assert "ledger.charge" in full["steps"][-1]["statement"]
    assert sum("[CROSS-SERVICE]" in s["step_role"] for s in full["steps"]) == 2


# --------------------------------------------------------------------------- #
# non-HTTP (Kafka) hop between Go and Java
# --------------------------------------------------------------------------- #

@pytest.fixture
def kafka_chain(tmp_path):
    producer = _svc(tmp_path, "ingest", "go", role="gateway")
    consumer = _svc(tmp_path, "roles", "java")

    _seed(producer, {
        "FlowSourceSink.json": {"grouped_flows": {}},
        "Flow2Out.json": _f2o("ingest.go:12", "ingest.go:14",
                              'producer.SendMessage(&sarama.ProducerMessage{Topic: "user.role-events", Value: role})',
                              "Ingest@ingest.go:8", flow_id="i0"),
        "interservice.json": {"outbound_calls": [{
            "id": "out_0", "protocol": "kafka", "method": None,
            "channel": "user.role-events",
            "file": "ingest.go", "line": 14, "location": "ingest.go:14",
            "flow_ref": "i0", "enclosing_function": "Ingest@ingest.go:8",
        }]},
        "endpoints.json": {"endpoints": []},
    })
    _seed(consumer, {
        "FlowSourceSink.json": _s2s("Consumer.java:30", "Consumer.java:34",
                                    "String role = record.value();",
                                    "userService.setРоль(user, role); // privileged",
                                    "onMessage@Consumer.java:25"),
        "Flow2Out.json": {"grouped_flows": {}},
        "interservice.json": {"outbound_calls": []},
        "endpoints.json": {"endpoints": [{
            "id": "ep_0", "protocol": "kafka", "method": None, "route": "user.role-events",
            "handler": "onMessage@Consumer.java:25", "handler_name": "onMessage",
            "file": "Consumer.java", "line": 25,
        }]},
    })
    return Application(name="events", services=[producer, consumer])


def test_kafka_cross_language_hop(kafka_chain):
    g = build_graph(kafka_chain)
    inter = [e for e in g.edges if e.kind == "inter_call"]
    assert inter, "kafka outbound was not matched to the consumer topic"
    assert inter[0].score == 1.0
    assert inter[0].data["from_service"] == "ingest"
    assert inter[0].data["to_service"] == "roles"

    doc = stitch(kafka_chain, g)
    flows = [f for fl in doc["grouped_flows"].values() for f in fl]
    assert any(f["hop_count"] == 1 and f["services"] == ["ingest", "roles"] for f in flows)
    f = next(f for f in flows if f["hop_count"] == 1)
    assert f["sink_location"].startswith("services/roles/")
    assert f["channels"] == ["user.role-events"]
