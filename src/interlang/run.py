"""
Orchestration for cross-service / cross-language analysis.

Stages
------
``global_flow_main``      run ``Qinter`` extraction per service, build the global
                          reachability graph (Algorithm 1) and stitch flows.
``validate_global_flows`` validate the stitched flows with the existing
                          LLM + Z3 validator over a multi-service call graph.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from common.helper import (
    AnalysisStatus,
    check_status,
    ensure_directory_exists,
    get_global_flow_json_file,
    get_global_graph_json_file,
    get_global_validation_dir,
    get_global_workdir,
    update_status,
)
from common.services import Application, load_application

from .extract import extract_endpoints, extract_interservice
from .graph import build_graph
from .stitch import stitch


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _symlink_farm(app: Application) -> Path:
    """
    Build ``<global-workdir>/services/<svc>`` symlinks to each service's real
    source tree so the ``services/<svc>/…`` paths in stitched flows resolve.
    """
    root = get_global_workdir(app.name)
    farm = root / "services"
    ensure_directory_exists(farm)
    for svc in app.services:
        link = farm / svc.name
        target = Path(svc.source_dir).resolve()
        try:
            if link.is_symlink() or link.exists():
                if link.is_symlink() and Path(os.readlink(link)) == target:
                    continue
                link.unlink()
            link.symlink_to(target, target_is_directory=True)
        except OSError as exc:  # pragma: no cover - platform dependent
            print(f"[interlang] could not link {link} -> {target}: {exc}")
    return root


def _warn_missing_prereqs(app: Application) -> None:
    for svc in app.services:
        if not check_status(svc.key, AnalysisStatus.FIND_FLOWS):
            print(
                f"  ! service '{svc.name}' ({svc.key}) has no FIND_FLOWS result yet — "
                f"run:  python main.py --app {svc.key} --find-sinks --find-flows"
            )


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def build_global_flows(app: Application, run_codeql: bool = True, refresh: bool = False) -> Path:
    print(f"[interlang] extracting inter-service communication for {len(app.services)} services")
    for svc in app.services:
        inter = extract_interservice(svc, run_codeql=run_codeql, refresh=refresh)
        eps = extract_endpoints(svc, run_codeql=run_codeql, refresh=refresh)
        print(
            f"  - {svc.name:<20} outbound={len(inter.get('outbound_calls', []))!s:<4} "
            f"endpoints={len(eps.get('endpoints', []))}"
        )
        if run_codeql:
            update_status(svc.key, AnalysisStatus.INTERSERVICE)
            update_status(svc.key, AnalysisStatus.ENDPOINTS)

    g = build_graph(app)
    graph_file = get_global_graph_json_file(app.name)
    graph_file.write_text(json.dumps(g.to_dict(), indent=2))

    doc = stitch(app, g)
    out = get_global_flow_json_file(app.name)
    out.write_text(json.dumps(doc, indent=2))

    s = doc["summary"]
    print(
        f"[interlang] global graph: {len(g.nodes)} nodes / {len(g.edges)} edges  ->  "
        f"{s['total_flows']} cross-service flows in {s['total_groups']} sink groups"
    )
    if doc["metadata"].get("path_search_truncated"):
        print("[interlang] ! path search hit a cap — some deep/duplicate flows were dropped "
              "(tune max_paths / max_paths_per_sink in interlang.graph)")
    print(f"[interlang] wrote {out}")
    return out


# ---------------------------------------------------------------------------
# CLI stages
# ---------------------------------------------------------------------------

def global_flow_main(appname: str, run_codeql: bool = True) -> int:
    app = load_application(appname)
    if not app.is_multi_service:
        print(
            f"[interlang] '{appname}' resolves to a single service; nothing to stitch.\n"
            f"            Add a manifest (codebases/<name>/neo.services.yaml) listing "
            f"multiple services to enable cross-language flows."
        )
        return 0

    print(f"[interlang] application '{app.name}' — services: {', '.join(s.name for s in app.services)}")
    _warn_missing_prereqs(app)
    build_global_flows(app, run_codeql=run_codeql)
    _symlink_farm(app)
    update_status(app.name, AnalysisStatus.GLOBAL_FLOWS)
    return 0


def validate_global_flows(llm_client, appname: str, max_validation_group: Optional[int] = None) -> int:
    import asyncio

    from flows.validate_flows import IterativeFlowValidator

    app = load_application(appname)
    if not app.is_multi_service:
        print(f"[interlang] '{appname}' is single-service; use --validate-flows instead.")
        return 0

    if check_status(app.name, AnalysisStatus.VALIDATE_GLOBAL_FLOWS):
        print(f"[interlang] {AnalysisStatus.VALIDATE_GLOBAL_FLOWS} already done for '{app.name}' "
              f"(clear status/{app.name}.{AnalysisStatus.VALIDATE_GLOBAL_FLOWS} to re-run)")
        return 0

    flow_file = get_global_flow_json_file(app.name)
    if not flow_file.exists():
        print("[interlang] global flow file missing — building it first")
        build_global_flows(app, run_codeql=False)

    # ensure a per-service call graph exists for function resolution
    from duck_db.create_duckdb import duckdb_main

    service_dbs, service_roots = {}, {}
    for svc in app.services:
        ddb = svc.duckdb_path
        if not ddb.exists():
            print(f"[interlang] building call graph for service '{svc.name}'")
            try:
                duckdb_main(svc.database_dir, svc.source_dir, svc.key)
            except Exception as exc:
                print(f"  ! could not build call graph for {svc.name}: {exc}")
        service_dbs[svc.name] = ddb
        service_roots[svc.name] = Path(svc.source_dir)

    farm_root = _symlink_farm(app)

    from .multidb import MultiServiceCallGraph

    db = MultiServiceCallGraph(service_dbs, service_roots)
    output_dir = get_global_validation_dir(app.name)
    validator = IterativeFlowValidator(llm_client, db, farm_root, output_dir, cross_service=True)

    if max_validation_group is None:
        env_cap = os.getenv("MAX_VALIDATION_GROUPS")
        if env_cap and env_cap.isdigit():
            max_validation_group = int(env_cap)

    max_concurrent = int(os.getenv("MAX_CONCURRENT_GROUPS", "3"))
    max_iterations = int(os.getenv("MAX_ITERATIONS", "5"))
    asyncio.run(
        validator.validate_flow_groups_concurrent(
            flow_file, max_validation_group, max_concurrent, max_iterations
        )
    )
    db.close()
    update_status(app.name, AnalysisStatus.VALIDATE_GLOBAL_FLOWS)
    print(f"[interlang] cross-service validation results in {output_dir}")
    return 0
