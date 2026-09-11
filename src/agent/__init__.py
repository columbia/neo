"""
Paper-aligned agentic layer.

* :mod:`agent.primitives` — the unified code-search primitives
  (``Qname / Qast / Qflow / Qcg / Qsource / Qinter / Qglobalflow``) plus the
  property functions (``get_location / get_source / get_type``), abstracting the
  per-language CodeQL + DuckDB call-graph machinery behind one interface.
* :mod:`agent.loop` — the perception-action loop that lets an LLM compose those
  primitives to identify privileged operations, trace flows and validate checks.
"""
