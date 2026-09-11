"""
Extraction layer: the CodeQL SARIF-message contract that every
``queries/<lang>/interservice.ql`` / ``endpoints.ql`` must satisfy, plus the
language-agnostic heuristic fallbacks.
"""

import json

import pytest

from common.services import Service
from interlang import extract as ex


# --------------------------------------------------------------------------- #
# CodeQL message contract
# --------------------------------------------------------------------------- #

def test_parse_inter_message():
    rec = ex._parse_inter_message(
        "INTER|http|POST|http://user-mgmt:5000/setUserRole|"
        "src/Ctl.java:14|updateProfile@src/Ctl.java:3"
    )
    assert rec == {
        "protocol": "http", "method": "POST",
        "channel": "http://user-mgmt:5000/setUserRole",
        "file": "src/Ctl.java", "line": 14, "location": "src/Ctl.java:14",
        "enclosing_function": "updateProfile@src/Ctl.java:3",
    }


def test_parse_inter_message_kafka_no_verb():
    rec = ex._parse_inter_message("INTER|kafka||order-events|p/producer.go:20|Publish@p/producer.go:10")
    assert rec["protocol"] == "kafka"
    assert rec["method"] is None
    assert rec["channel"] == "order-events"


def test_parse_endpoint_message():
    rec = ex._parse_endpoint_message("ENDPOINT|http|POST|/api/setUserRole|set_role@app/main.py:20")
    assert rec["method"] == "POST"
    assert rec["route"] == "/api/setUserRole"
    assert rec["handler_name"] == "set_role"
    assert rec["file"] == "app/main.py" and rec["line"] == 20


def test_parse_rejects_foreign_lines():
    assert ex._parse_inter_message("something else") is None
    assert ex._parse_endpoint_message("INTER|http|GET|/x|h@f:1") is None


def test_iter_messages_reads_sarif(tmp_path):
    sarif = {
        "runs": [{
            "results": [
                {"message": {"text": "INTER|http|GET|/ping|f.js:2|h@f.js:1"},
                 "locations": [{"physicalLocation": {
                     "artifactLocation": {"uri": "f.js"},
                     "region": {"startLine": 2, "startColumn": 1}}}]},
                {"message": {"text": "ENDPOINT|http|POST|/orders|create@f.js:9"}},
            ]
        }]
    }
    f = tmp_path / "q.sarif"
    f.write_text(json.dumps(sarif))
    msgs = [m for m, _loc in ex._iter_messages(f)]
    assert msgs[0].startswith("INTER|")
    assert msgs[1].startswith("ENDPOINT|")


# --------------------------------------------------------------------------- #
# heuristic endpoint scan across languages
# --------------------------------------------------------------------------- #

def _svc(tmp_path, lang, filename, code):
    d = tmp_path / f"{lang}-svc"
    (d / "sub").mkdir(parents=True)
    (d / "sub" / filename).write_text(code)
    return Service(name=f"{lang}-svc", role="internal", app=f"{lang}-svc",
                   source_dir=d, database_dir=d, _language=lang)


@pytest.mark.parametrize("lang,fname,code,want", [
    ("go", "router.go",
     'func setup(r *gin.Engine) {\n\tr.POST("/users/:id/role", updateRole)\n\tr.GET("/health", ping)\n}\n',
     {("POST", "/users/:id/role"), ("GET", "/health")}),
    ("javascript", "routes.js",
     "const router = require('express').Router()\n"
     "router.post('/setUserRole', async (req, res) => {})\n"
     "app.get('/status', status)\n",
     {("POST", "/setUserRole"), ("GET", "/status")}),
    ("csharp", "Ctl.cs",
     '[HttpPost("setUserRole")]\npublic async Task<IActionResult> SetRole() { }\n'
     '[HttpGet("me")]\npublic IActionResult Me() { }\n',
     {("POST", "setUserRole"), ("GET", "me")}),
    ("python", "app.py",
     'from fastapi import APIRouter\nr = APIRouter()\n'
     '@r.put("/roles/{name}")\nasync def put_role():\n    pass\n',
     {("PUT", "/roles/{name}")}),
])
def test_heuristic_endpoint_scan_multilang(tmp_path, lang, fname, code, want):
    svc = _svc(tmp_path, lang, fname, code)
    payload = ex.extract_endpoints(svc, run_codeql=False, refresh=True)
    got = {(e["method"], e["route"].lstrip("/") if lang == "csharp" else e["route"])
           for e in payload["endpoints"]}
    # routes are normalised to a leading slash except the raw C# attribute value
    got = {(m, r if r.startswith("/") or lang == "csharp" else "/" + r) for (m, r) in got}
    assert want <= got, f"{lang}: missing {want - got} (got {got})"


def test_heuristic_spring_class_prefix_not_an_endpoint(tmp_path):
    svc = _svc(tmp_path, "java", "Ctl.java", (
        "@RestController\n"
        '@RequestMapping("/api")\n'
        "public class Ctl {\n"
        '    @PostMapping("/setUserRole")\n'
        "    public String setRole(@RequestBody Req r) { return svc.set(r); }\n"
        "}\n"
    ))
    payload = ex.extract_endpoints(svc, run_codeql=False, refresh=True)
    routes = {(e["method"], e["route"]) for e in payload["endpoints"]}
    assert ("POST", "/api/setUserRole") in routes
    # the bare class-level @RequestMapping("/api") must not appear on its own
    assert not any(r == "/api" for _m, r in routes)


def test_heuristic_outbound_kafka_topic(tmp_path):
    svc = Service(name="producer", role="gateway", app="producer",
                  source_dir=tmp_path / "p", database_dir=tmp_path / "p", _language="go")
    (tmp_path / "p" / "neo-workdir").mkdir(parents=True)
    (tmp_path / "p" / "neo-workdir" / "Flow2Out.json").write_text(json.dumps({
        "grouped_flows": {"h.go:1": [{
            "flow_id": "f0", "source_location": "h.go:1", "sink_location": "h.go:5",
            "steps": [{"step_role": "Step 1", "statement": "role := r.FormValue(\"role\")",
                       "location": "h.go:1", "file": "h.go", "function_id": "N/A", "role": "source"},
                      {"step_role": "Step 2",
                       "statement": 'producer.SendMessage(&sarama.ProducerMessage{Topic: "user.role-events", Value: role})',
                       "location": "h.go:5", "file": "h.go", "function_id": "N/A", "role": "sink"}],
        }]}
    }))
    payload = ex.extract_interservice(svc, run_codeql=False, refresh=True)
    calls = payload["outbound_calls"]
    assert calls and calls[0]["protocol"] == "kafka"
    assert calls[0]["channel"] == "user.role-events"
