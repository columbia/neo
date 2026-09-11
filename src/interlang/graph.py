"""
Global cross-service reachability graph  (paper Algorithm 1 / ``Qglobalflow``).

Phase 1 — intra-service edges, per service:
  * every ``source -> privileged sink`` flow  (from ``FlowSourceSink.json``)
  * every ``source -> outbound call`` flow     (from ``Flow2Out.json`` + ``interservice.json``)

Phase 2 — inter-service edges:
  * ``outbound call (svc A) -> inbound endpoint (svc B)`` when the outbound
    channel identifier matches the endpoint route (see :mod:`interlang.channels`)
  * ``inbound endpoint (svc B) -> source (svc B)`` linking the request into the
    handler's tainted sources

The engine then enumerates paths from user-facing entry sources to privileged
sinks.  Each path carries the concatenated, service-prefixed flow steps so the
existing validator can consume it unchanged.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from .channels import Channel, Endpoint, match_channel

# artifact file names inside a service's ``neo-workdir``
F_SINK = "FlowSourceSink.json"
F_OUT = "Flow2Out.json"
F_INTER = "interservice.json"
F_ENDPOINTS = "endpoints.json"

ENTRY, SOURCE, BOUNDARY, ENDPOINT_N, SINK = "entry", "source", "boundary", "endpoint", "sink"


@dataclass
class Node:
    id: str
    kind: str
    service: str
    ref: str                       # location or endpoint/outbound id
    data: dict = field(default_factory=dict)


@dataclass
class Edge:
    src: str
    dst: str
    kind: str                      # intra_flow | inter_call | enters
    steps: List[dict] = field(default_factory=list)
    score: float = 1.0
    data: dict = field(default_factory=dict)


class GlobalGraph:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self._adj: Dict[str, List[Edge]] = defaultdict(list)

    # -- construction ---------------------------------------------------------
    def add_node(self, kind: str, service: str, ref: str, **data) -> str:
        nid = f"{kind}:{service}:{ref}"
        if nid not in self.nodes:
            self.nodes[nid] = Node(nid, kind, service, ref, data)
        else:
            self.nodes[nid].data.update(data)
        return nid

    def add_edge(self, src: str, dst: str, kind: str, steps=None, score: float = 1.0, **data):
        e = Edge(src, dst, kind, steps or [], score, data)
        self.edges.append(e)
        self._adj[src].append(e)

    #: set True by paths() when a cap stopped the search (so callers can warn)
    truncated: bool = False

    # -- traversal ----------------------------------------------------------
    def paths(self, max_depth: int = 14, max_paths: int = 4000,
              max_paths_per_sink: int = 40) -> List[List[Edge]]:
        """
        Enumerate simple entry→sink paths.

        Caps keep a densely connected graph from exploding: ``max_paths`` total,
        ``max_paths_per_sink`` per privileged sink, ``max_depth`` edges deep.
        ``self.truncated`` is set if any cap fired.
        """
        starts = [n.id for n in self.nodes.values() if n.kind == ENTRY]
        out: List[List[Edge]] = []
        per_sink: Dict[str, int] = defaultdict(int)
        self.truncated = False

        def dfs(nid: str, trail: List[Edge], seen: set, svcs: List[str]):
            if len(trail) > max_depth or len(out) >= max_paths:
                self.truncated = True
                return
            if self.nodes[nid].kind == SINK and trail:
                if per_sink[nid] >= max_paths_per_sink:
                    self.truncated = True
                    return
                per_sink[nid] += 1
                out.append(list(trail))
                return
            for e in self._adj.get(nid, []):
                if e.dst in seen:
                    continue
                # never re-enter a service already on this path (kills A->B->A bounce)
                nxt = self.nodes[e.dst].service
                if e.kind == "inter_call" and nxt in svcs:
                    continue
                seen.add(e.dst)
                trail.append(e)
                dfs(e.dst, trail, seen, svcs + [nxt] if nxt not in svcs else svcs)
                trail.pop()
                seen.discard(e.dst)

        for s in starts:
            dfs(s, [], {s}, [self.nodes[s].service])
        return out

    def to_dict(self) -> dict:
        return {
            "nodes": [vars(n) for n in self.nodes.values()],
            "edges": [
                {"src": e.src, "dst": e.dst, "kind": e.kind, "score": e.score,
                 "step_count": len(e.steps), **e.data}
                for e in self.edges
            ],
        }


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------

def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        return {}


def _prefix_steps(steps: List[dict], svc: str) -> List[dict]:
    """Namespace a flow's file paths with ``services/<svc>/`` for the validator."""
    pre = f"services/{svc}/"
    out = []
    for s in steps:
        s = dict(s)
        f = s.get("file", "")
        if f and not f.startswith(pre):
            s["file"] = pre + f
        loc = s.get("location", "")
        if loc and not loc.startswith(pre):
            s["location"] = pre + loc
        fid = s.get("function_id", "")
        if fid and "@" in fid and pre not in fid:
            name, _, floc = fid.partition("@")
            s["function_id"] = f"{name}@{pre}{floc}"
        s["service"] = svc
        out.append(s)
    return out


def _flow_sink_loc(flow: dict) -> str:
    steps = flow.get("steps") or []
    return steps[-1].get("location", "") if steps else flow.get("sink_location", "")


def _in_handler(oc: dict, ep: Endpoint, all_eps: List[Endpoint]) -> bool:
    """Is the outbound call *oc* (file:line) inside endpoint *ep*'s handler body?"""
    ocf = (oc.get("file") or "").strip()
    if not ocf or not ep.file or not (ocf == ep.file or ocf.endswith(ep.file) or ep.file.endswith(ocf)):
        return False
    ln = int(oc.get("line") or 0)
    if not ep.line or ln < ep.line or ln - ep.line > 150:
        return False
    # no other handler in the same file starts between ep and the call
    for other in all_eps:
        if other is ep or other.file != ep.file:
            continue
        if ep.line < other.line <= ln:
            return False
    return True


def build_graph(app, *, max_channel_matches: int = 2, min_score: float = 0.4) -> GlobalGraph:
    g = GlobalGraph()

    per_svc_endpoints: Dict[str, List[Endpoint]] = {}
    per_svc_outbound: Dict[str, List[dict]] = {}
    per_svc_sources: Dict[str, List[Tuple[str, str, dict]]] = defaultdict(list)  # (src_loc, file, flow)

    # ---- Phase 1: intra-service ----
    for svc in app.services:
        name = svc.name
        wd = svc.workdir
        s2s = _load(wd / F_SINK)
        f2o = _load(wd / F_OUT)
        inter = _load(wd / F_INTER)
        eps_raw = _load(wd / F_ENDPOINTS)

        per_svc_endpoints[name] = [
            Endpoint(
                service=name, kind=e.get("protocol", "http"),
                method=(e.get("method") or None), path=e.get("route", "/"),
                topic=(e.get("route") if e.get("protocol") in ("kafka", "rabbitmq", "grpc") else None),
                handler_id=e.get("handler", ""), handler_name=e.get("handler_name", ""),
                file=e.get("file", ""), line=int(e.get("line") or 0), raw=e.get("route", ""),
            )
            for e in (eps_raw.get("endpoints") or [])
        ]

        # source -> privileged sink
        for _grp, flows in (s2s.get("grouped_flows") or {}).items():
            for flow in flows:
                src_loc = flow.get("source_location", "")
                sink_loc = flow.get("sink_location", "")
                if not src_loc or not sink_loc:
                    continue
                snode = g.add_node(SOURCE, name, src_loc, file=src_loc.split(":")[0])
                knode = g.add_node(SINK, name, sink_loc, file=sink_loc.split(":")[0])
                g.add_edge(snode, knode, "intra_flow",
                           steps=_prefix_steps(flow.get("steps") or [], name),
                           flow_id=flow.get("flow_id", ""), service=name)
                per_svc_sources[name].append((src_loc, src_loc.split(":")[0], flow))

        # source -> outbound call  (link Flow2Out flow to an interservice outbound record)
        outbound = inter.get("outbound_calls") or []
        per_svc_outbound[name] = outbound
        by_loc: Dict[str, List[dict]] = defaultdict(list)
        by_flowref: Dict[str, List[dict]] = defaultdict(list)
        for oc in outbound:
            if oc.get("location"):
                by_loc[oc["location"]].append(oc)
            if oc.get("flow_ref"):
                by_flowref[oc["flow_ref"]].append(oc)

        for _grp, flows in (f2o.get("grouped_flows") or {}).items():
            for flow in flows:
                src_loc = flow.get("source_location", "")
                if not src_loc:
                    continue
                matches = by_flowref.get(flow.get("flow_id", "")) or by_loc.get(_flow_sink_loc(flow)) or []
                if not matches and len(outbound) == 1:
                    # sole outbound call: only attach if it plausibly sits on this
                    # flow (same file as the flow's last step / declared sink)
                    only = outbound[0]
                    flow_sink_file = (_flow_sink_loc(flow) or flow.get("sink_location", "")).split(":")[0]
                    if only.get("file") and flow_sink_file and (
                        only["file"] == flow_sink_file or flow_sink_file.endswith(only["file"])
                        or only["file"].endswith(flow_sink_file)
                    ):
                        matches = outbound
                    elif not only.get("file"):
                        matches = outbound  # nothing to disambiguate on
                for oc in matches:
                    snode = g.add_node(SOURCE, name, src_loc, file=src_loc.split(":")[0])
                    bnode = g.add_node(BOUNDARY, name, oc["id"],
                                       channel=oc.get("channel", ""), protocol=oc.get("protocol", "http"),
                                       method=oc.get("method"), file=oc.get("file", ""), line=oc.get("line", 0),
                                       location=oc.get("location", ""))
                    g.add_edge(snode, bnode, "intra_flow",
                               steps=_prefix_steps(flow.get("steps") or [], name),
                               flow_id=flow.get("flow_id", ""), service=name)
                    per_svc_sources[name].append((src_loc, src_loc.split(":")[0], flow))

    # ---- endpoints as nodes; gateway endpoints as entries; handler -> outbound ----
    entry_services = {s.name for s in app.gateway_services()}
    for svc in app.services:
        name = svc.name
        eps = per_svc_endpoints.get(name, [])
        ocs = per_svc_outbound.get(name, [])
        for ep in eps:
            ep_ref = ep.handler_id or f"{ep.file}:{ep.line}"
            epn = g.add_node(ENDPOINT_N, name, ep_ref,
                             route=ep.path, method=ep.method, protocol=ep.kind,
                             handler=ep.handler_id, handler_name=ep.handler_name,
                             file=ep.file, line=ep.line)
            if name in entry_services:
                en = g.add_node(ENTRY, name, f"ep:{ep_ref}", **g.nodes[epn].data)
                g.add_edge(en, epn, "enters", score=1.0, service=name)
            # a request handler that itself makes an inter-service call (gateway/BFF pattern)
            for oc in ocs:
                if _in_handler(oc, ep, eps):
                    bn = g.add_node(BOUNDARY, name, oc["id"],
                                    channel=oc.get("channel", ""), protocol=oc.get("protocol", "http"),
                                    method=oc.get("method"), file=oc.get("file", ""),
                                    line=oc.get("line", 0), location=oc.get("location", ""))
                    g.add_edge(epn, bn, "handler_calls", service=name,
                               handler=ep.handler_name, route=ep.path)

    # ---- mark entry sources (tainted RemoteFlowSource in a gateway service) ----
    for nid, node in list(g.nodes.items()):
        if node.kind == SOURCE and node.service in entry_services:
            enode = g.add_node(ENTRY, node.service, node.ref, **node.data)
            g.add_edge(enode, nid, "enters", score=1.0, service=node.service)

    # ---- Phase 2: inter-service edges ----
    for nid, node in list(g.nodes.items()):
        if node.kind != BOUNDARY:
            continue
        ch = Channel.parse(node.data.get("channel", ""), kind=node.data.get("protocol", "http"),
                           method=node.data.get("method"))
        node.data["channel_parsed"] = ch.to_dict()
        for tgt in app.services:
            if tgt.name == node.service:
                continue
            ranked = match_channel(ch, per_svc_endpoints.get(tgt.name, []),
                                   service_tokens=tgt.match_tokens(), base_path=tgt.base_path,
                                   min_score=min_score)
            for ep, score in ranked[:max_channel_matches]:
                ep_ref = ep.handler_id or f"{ep.file}:{ep.line}"
                epnode = g.add_node(ENDPOINT_N, tgt.name, ep_ref,
                                    route=ep.path, method=ep.method, protocol=ep.kind,
                                    handler=ep.handler_id, handler_name=ep.handler_name,
                                    file=ep.file, line=ep.line)
                g.add_edge(nid, epnode, "inter_call", score=score,
                           channel=ch.raw, from_service=node.service, to_service=tgt.name)
                _connect_endpoint_to_sources(g, epnode, ep, tgt.name, per_svc_sources.get(tgt.name, []))

    return g


def _connect_endpoint_to_sources(g: GlobalGraph, epnode: str, ep: Endpoint, svc: str,
                                 sources: List[Tuple[str, str, dict]]):
    """
    Link an inbound endpoint to the request-tainted sources of *its handler*.

    Conservative on purpose: an endpoint is wired only to sources in the same
    file (ideally within a window below the handler line).  If nothing in the
    handler's file is a tainted source we do NOT fall back to "every source in
    the service" — that fabricates cross-service flows through unrelated code.
    The single exception is a service with exactly one distinct source file,
    where the target is unambiguous.
    """
    ep_file = ep.file
    linked = 0

    same_file = [(loc, f, fl) for (loc, f, fl) in sources if ep_file and f.endswith(ep_file)]
    if same_file:
        for src_loc, _f, _flow in same_file:
            try:
                src_line = int(src_loc.rsplit(":", 1)[-1])
            except ValueError:
                src_line = 0
            # keep sources at/after the handler definition (params, request reads)
            if ep.line and src_line and not (0 <= src_line - ep.line <= 600):
                continue
            snode = g.add_node(SOURCE, svc, src_loc, file=src_loc.split(":")[0])
            g.add_edge(epnode, snode, "enters", score=0.9, service=svc)
            linked += 1
        if linked:
            return linked

    distinct_files = {f for (_loc, f, _fl) in sources}
    if len(distinct_files) == 1:
        for src_loc, _f, _flow in sources:
            snode = g.add_node(SOURCE, svc, src_loc, file=src_loc.split(":")[0])
            g.add_edge(epnode, snode, "enters", score=0.4, service=svc)
            linked += 1
    return linked
