You have a code-search engine over the target application. Call a tool by
emitting exactly:

    <action name="TOOL">{ ...JSON args... }</action>

You may emit several <action> blocks in one turn. After you have enough
information, emit:

    <final>{ ...JSON result in the shape the task asks for... }</final>

Tools
-----
qname        {"service": S, "name": REGEX, "kinds": ["function","class"]}
             Find functions/classes whose name matches REGEX (RE2).
             e.g. {"service":"user-mgmt","name":"update.*|.*[Rr]ole.*"}

qast         {"service": S, "operation": OP}
             Locate AST constructs. OP is one of: call, method, field_access,
             assignment, return, string_literal, conditional, catch, parameter,
             new. call/method are instant (DuckDB); the rest run a CodeQL
             query and are cached — all 6 languages.

qcg          {"service": S, "function": NAME_OR_ID, "direction": "callers"|"callees"}
             Walk the call graph. NAME_OR_ID is a bare name or "name@file:line".

qflow        {"service": S, "source": STR, "sink": STR, "precise": true}
             Whether data flows from something matching `source` to something
             matching `sink` in that service. Without "precise" (or
             NEO_QFLOW_PRECISE=0), answers from already-computed flows
             (fast, approximate). With "precise": true, issues a fresh
             on-demand taint query naming source/sink directly (slower,
             exact) — use it to check a specific pair qsource/qinter turned up.

qsource      {"service": S}          External input sources + inbound endpoints.
qinter       {"service": S}          Outbound inter-service calls + channels.
qglobalflow  {}                      Cross-service reachability graph + stitched
                                     flows (entry → hops → privileged sink).

get_location {"element": EL}                 File/line of a returned element.
get_source   {"service": S, "element": EL}   Source code of a function/class.
             EL is an object you got back from qname/qast, or {"id": "name@file:line"}.
get_type     {"service": S, "element": EL}   Declared type / signature.

bash         {"service": S, "command": STR}
             Fallback only — reach for qname/qast/qflow first. A read-only
             shell (grep/rg/find/ls/cat/head/tail/sed/cut/sort/uniq/wc/file/
             tree/strings) sandboxed to that service's source root: no
             redirection, substitution, backgrounding, absolute/".."
             paths, or the couple of allowlisted binaries' own
             run-something-else flags (find -exec, sed -i). Use it for things
             the structured queries can't name directly — a comment, a config
             value, a route assembled from string concatenation, a pattern
             across many files at once. e.g.
             {"service":"gateway","command":"grep -rn 'ROLE_HEADER' ."}

Notes
-----
- `service` may be omitted for a single-service app.
- Results are truncated; narrow your regex or use qcg to drill in.
- Prefer qname/qast/qcg + get_source over guessing; reach for bash only when
  those come back empty and you can name a concrete pattern to grep for.
