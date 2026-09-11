"""
Turn cross-service reachability paths into the ``FlowSourceSink.json`` schema
that :mod:`flows.validate_flows` already understands, so global flows are
validated by exactly the same LLM + Z3 pipeline as intra-service ones.

Each stitched flow's steps are the concatenation of the per-service flow steps
along the path, with a synthetic ``[CROSS-SERVICE]`` step inserted at every
inter-service hop.  File paths are namespaced ``services/<svc>/…`` so the
multi-service source root resolves them.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .graph import Edge, GlobalGraph


def _hop_step(g: GlobalGraph, edge: Edge, index: int) -> dict:
    b = g.nodes[edge.src].data
    e = g.nodes[edge.dst].data
    from_svc = edge.data.get("from_service", g.nodes[edge.src].service)
    to_svc = edge.data.get("to_service", g.nodes[edge.dst].service)
    channel = edge.data.get("channel", b.get("channel", ""))
    route = e.get("route", "")
    bfile = b.get("file", "")
    bline = b.get("line", 0)
    loc = f"services/{from_svc}/{bfile}:{bline}" if bfile else f"{from_svc}:outbound"
    handler = e.get("handler") or ""
    if handler and "@" in handler and f"services/{to_svc}/" not in handler:
        _n, _, _fl = handler.partition("@")
        handler = f"{_n}@services/{to_svc}/{_fl}"
    return {
        "step_role": f"Step {index} [CROSS-SERVICE]",
        "statement": f"// inter-service call: {from_svc} --[{channel or '?'}]--> {to_svc} endpoint {route or '?'}",
        "location": loc,
        "file": f"services/{from_svc}/{bfile}" if bfile else from_svc,
        "role": "step",
        "function_id": handler or "N/A",
        "cross_service": {
            "from_service": from_svc, "to_service": to_svc,
            "channel": channel, "route": route,
            "endpoint_handler": e.get("handler", ""), "match_score": edge.score,
        },
    }


def path_to_flow(g: GlobalGraph, path: List[Edge], flow_id: str) -> dict:
    steps: List[dict] = []
    services: List[str] = []
    channels: List[str] = []
    hops = 0

    for edge in path:
        svc = edge.data.get("service") or g.nodes[edge.src].service
        if svc and (not services or services[-1] != svc):
            services.append(svc)
        if edge.kind == "intra_flow":
            steps.extend(edge.steps)
        elif edge.kind == "handler_calls":
            b = g.nodes[edge.dst].data
            bfile = b.get("file", "")
            steps.append({
                "step_role": f"Step {len(steps) + 1}",
                "statement": f"// {edge.data.get('route', '?')} handler "
                             f"{edge.data.get('handler', '')} issues outbound call "
                             f"[{b.get('channel', '?')}]",
                "location": f"services/{svc}/{bfile}:{b.get('line', 0)}" if bfile else f"{svc}:handler",
                "file": f"services/{svc}/{bfile}" if bfile else svc,
                "role": "step", "function_id": "N/A", "service": svc,
            })
        elif edge.kind == "inter_call":
            hops += 1
            steps.append(_hop_step(g, edge, len(steps) + 1))
            ch = edge.data.get("channel")
            if ch:
                channels.append(ch)
            to_svc = edge.data.get("to_service")
            if to_svc and (not services or services[-1] != to_svc):
                services.append(to_svc)
        # "enters" edges carry no steps

    # collapse consecutive steps that point at the same statement+location
    # (CodeQL path graphs often emit several path nodes on one line)
    deduped: List[dict] = []
    for s in steps:
        prev = deduped[-1] if deduped else None
        if prev and s.get("location") == prev.get("location") \
                and s.get("statement") == prev.get("statement"):
            continue
        deduped.append(s)
    steps = deduped

    # renumber step roles, keep SOURCE/SINK tags
    for i, s in enumerate(steps):
        tag = ""
        if i == 0:
            tag = " [SOURCE]"
        elif i == len(steps) - 1:
            tag = " [SINK]"
        elif "[CROSS-SERVICE]" in s.get("step_role", ""):
            steps[i] = dict(s)
            steps[i]["step_role"] = f"Step {i + 1} [CROSS-SERVICE]"
            continue
        steps[i] = dict(s)
        steps[i]["step_role"] = f"Step {i + 1}{tag}"

    src_loc = steps[0]["location"] if steps else ""
    sink_loc = steps[-1]["location"] if steps else ""
    return {
        "flow_id": flow_id,
        "source_location": src_loc,
        "sink_location": sink_loc,
        "step_count": len(steps),
        "cross_service": True,
        "services": services,
        "hop_count": hops,
        "channels": channels,
        "steps": steps,
    }


def _summary(grouped: Dict[str, List[dict]]) -> dict:
    total_flows = sum(len(v) for v in grouped.values())
    groups = []
    total_funcs = 0
    for gk, flows in grouped.items():
        funcs = set()
        svcs = set()
        for fl in flows:
            svcs.update(fl.get("services", []))
            for st in fl["steps"]:
                fid = st.get("function_id")
                if fid and fid != "N/A":
                    funcs.add(fid)
        total_funcs += len(funcs)
        groups.append({
            "group_key": gk,
            "flow_count": len(flows),
            "unique_sinks": 1,
            "unique_sources": len({fl["source_location"] for fl in flows}),
            "unique_functions": len(funcs),
            "services": sorted(svcs),
            "max_hop_count": max((fl.get("hop_count", 0) for fl in flows), default=0),
        })
    return {
        "grouping_type": "sinks",
        "total_groups": len(grouped),
        "total_flows": total_flows,
        "total_unique_functions": total_funcs,
        "groups": groups,
    }


def stitch(app, g: GlobalGraph, *, max_depth: int = 14) -> dict:
    raw_paths = g.paths(max_depth=max_depth)

    # de-duplicate: one flow per (sink, service chain, channel chain); when
    # several paths collapse to the same key keep the most detailed one (most
    # real, non-synthetic steps) — e.g. a genuine Flow2Out taint step beats the
    # `handler_calls` placeholder.
    best: Dict[tuple, dict] = {}
    for path in raw_paths:
        flow = path_to_flow(g, path, flow_id="")
        if not flow["steps"] or flow["hop_count"] < 1:
            continue
        key = (flow["sink_location"], tuple(flow["services"]), tuple(flow["channels"]))
        real = sum(1 for s in flow["steps"] if not s.get("statement", "").lstrip().startswith("//"))
        cur = best.get(key)
        if cur is None or real > cur[0]:
            best[key] = (real, flow)

    grouped: Dict[str, List[dict]] = defaultdict(list)
    for idx, (_real, flow) in enumerate(sorted(best.values(), key=lambda t: -t[0])):
        flow["flow_id"] = f"gflow_{idx}"
        grouped[flow["sink_location"]].append(flow)

    return {
        "metadata": {
            "application": app.name,
            "grouping_method": "sinks",
            "analysis": "cross_service_global_flow",
            "services": [s.name for s in app.services],
            "manifest": str(app.manifest_path) if app.manifest_path else None,
            "path_search_truncated": bool(getattr(g, "truncated", False)),
        },
        "summary": _summary(grouped),
        "grouped_flows": dict(grouped),
    }
