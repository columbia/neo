"""
Cross-service / cross-language flow analysis.

Implements the paper's ``Qinter`` (inter-service communication points +
channel identifiers) and ``Qglobalflow`` (Algorithm 1: a global reachability
graph that connects per-service data flows through matching
outbound-call / inbound-endpoint pairs).

Public entry point: :func:`interlang.run.global_flow_main`.
"""
