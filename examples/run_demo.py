#!/usr/bin/env python3
"""
Offline demo of the cross-service / cross-language flow engine.

Normally the per-service ``FlowSourceSink.json`` / ``Flow2Out.json`` come from
CodeQL (``python src/main.py --app <svc> --find-sinks --find-flows``).  Here we
synthesise them from the demo source files so the ``Qinter`` + ``Qglobalflow``
engine can be exercised without CodeQL, and print the stitched cross-service
flow it produces.

    python examples/run_demo.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from common.services import load_application          # noqa: E402
from interlang.run import build_global_flows          # noqa: E402

MANIFEST = ROOT / "examples" / "role-switch-demo" / "neo.services.yaml"


def _line_of(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"marker {needle!r} not found in {path}")


def seed(app):
    up = app.get("user-profile")
    um = app.get("user-mgmt")

    jctrl = up.source_dir / "src" / "ProfileController.java"
    src_ln = _line_of(jctrl, "req.getRole()")
    out_ln = _line_of(jctrl, "postForObject(")
    up.workdir.mkdir(parents=True, exist_ok=True)
    (up.workdir / "FlowSourceSink.json").write_text(json.dumps({"grouped_flows": {}}))
    (up.workdir / "Flow2Out.json").write_text(json.dumps({"grouped_flows": {
        f"src/ProfileController.java:{src_ln}": [{
            "flow_id": "flow_0_0_0",
            "source_location": f"src/ProfileController.java:{src_ln}",
            "sink_location": f"src/ProfileController.java:{out_ln}",
            "steps": [
                {"step_role": "Step 1 [SOURCE]", "statement": "req.getRole()",
                 "location": f"src/ProfileController.java:{src_ln}", "file": "src/ProfileController.java",
                 "function_id": "updateProfile@src/ProfileController.java:15", "role": "source"},
                {"step_role": "Step 2 [SINK]",
                 "statement": 'restTemplate.postForObject("http://localhost:5000/setUserRole", entity, String.class)',
                 "location": f"src/ProfileController.java:{out_ln}", "file": "src/ProfileController.java",
                 "function_id": "updateProfile@src/ProfileController.java:15", "role": "sink"},
            ],
        }]
    }}))

    pmain = um.source_dir / "app" / "main.py"
    p_src = _line_of(pmain, "await request.json()")
    p_sink = _line_of(pmain, "update_role(data.get")
    um.workdir.mkdir(parents=True, exist_ok=True)
    (um.workdir / "FlowSourceSink.json").write_text(json.dumps({"grouped_flows": {
        f"app/main.py:{p_sink}": [{
            "flow_id": "flow_0_0_0",
            "source_location": f"app/main.py:{p_src}",
            "sink_location": f"app/main.py:{p_sink}",
            "steps": [
                {"step_role": "Step 1 [SOURCE]", "statement": "data = await request.json()",
                 "location": f"app/main.py:{p_src}", "file": "app/main.py",
                 "function_id": "set_user_role@app/main.py:16", "role": "source"},
                {"step_role": "Step 2 [SINK]", "statement": "update_role(data.get('username'), data.get('role'))",
                 "location": f"app/main.py:{p_sink}", "file": "app/main.py",
                 "function_id": "set_user_role@app/main.py:16", "role": "sink"},
            ],
        }]
    }}))
    (um.workdir / "Flow2Out.json").write_text(json.dumps({"grouped_flows": {}}))


def main():
    app = load_application(str(MANIFEST))
    print(f"application: {app.name}  services: {[s.name for s in app.services]}")
    seed(app)
    out = build_global_flows(app, run_codeql=False)
    doc = json.loads(out.read_text())

    print("\n=== stitched cross-service flows ===")
    for sink, flows in doc["grouped_flows"].items():
        for f in flows:
            print(f"\n{f['flow_id']}  ({' -> '.join(f['services'])}, {f['hop_count']} hop)")
            print(f"  entry : {f['source_location']}")
            print(f"  sink  : {f['sink_location']}")
            for st in f["steps"]:
                print(f"    {st['step_role']:<26} {st['statement']}")
    print(f"\nfull document: {out}")


if __name__ == "__main__":
    main()
